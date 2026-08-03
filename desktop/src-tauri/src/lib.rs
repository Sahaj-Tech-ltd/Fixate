use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendState {
    process: Mutex<Option<Child>>,
    port: Mutex<Option<u16>>,
}

/// Find the fixate-backend binary relative to the current executable.
/// In dev mode, look in the project directory. In bundled mode, look next to the binary.
fn find_backend_binary() -> Option<std::path::PathBuf> {
    // Names to try on each path (Windows: PyInstaller appends .exe)
    let names: &[&str] = if cfg!(windows) {
        &["fixate-backend", "fixate-backend.exe"]
    } else {
        &["fixate-backend"]
    };

    // First: check next to the current executable (bundled mode)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            for name in names {
                let bundled = exe_dir.join(name);
                if bundled.exists() {
                    return Some(bundled);
                }
            }
        }
    }

    // Second: check the desktop/dist/ directory (dev mode, post-build)
    let mut candidates: Vec<String> = vec![
        "desktop/dist/fixate-backend".into(),
        "../desktop/dist/fixate-backend".into(),
        "./fixate-backend".into(),
        "/usr/lib/Fixate/fixate-backend".into(),
    ];
    if cfg!(windows) {
        candidates.push("desktop/dist/fixate-backend.exe".into());
        candidates.push("../desktop/dist/fixate-backend.exe".into());
    }

    for candidate in &candidates {
        let path = std::path::Path::new(candidate);
        if path.exists() {
            return Some(path.to_path_buf());
        }
    }

    // Third: check if fixate-backend is on PATH
    let (finder, args): (&str, &[&str]) = if cfg!(windows) {
        ("where", &["fixate-backend"])
    } else {
        ("which", &["fixate-backend"])
    };
    if let Ok(output) = Command::new(finder).args(args).output() {
        if output.status.success() {
            let path_str = String::from_utf8_lossy(&output.stdout).trim().to_string();
            // "where" can return multiple matches; take first line
            let first_line = path_str.lines().next().unwrap_or(&path_str);
            let path = std::path::PathBuf::from(first_line);
            if path.exists() {
                return Some(path);
            }
        }
    }

    None
}

/// Spawn the Django backend, read its port from stdout, and wait for readiness.
fn spawn_backend(binary_path: &std::path::Path) -> Result<(Child, u16), String> {
    let mut child = Command::new(binary_path)
        .env("FIXATE_MODE", "desktop")
        .env("DEBUG", "False")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn backend: {}", e))?;

    // Read the PORT:XXXXX line from stdout
    let stdout = child.stdout.take()
        .ok_or("Failed to capture backend stdout")?;

    let reader = BufReader::new(stdout);
    let mut port: Option<u16> = None;

    // Read lines until we get PORT:XXXXX or timeout after 10 seconds
    let start = std::time::Instant::now();
    for line in reader.lines() {
        if start.elapsed() > Duration::from_secs(10) {
            return Err("Backend timed out — no PORT line received".to_string());
        }
        match line {
            Ok(line) => {
                eprintln!("[backend] {}", line);
                if let Some(port_str) = line.strip_prefix("PORT:") {
                    port = Some(port_str.trim().parse::<u16>()
                        .map_err(|e| format!("Invalid port: {} — {}", port_str, e))?);
                    break;
                }
            }
            Err(e) => {
                eprintln!("[backend] read error: {}", e);
                break;
            }
        }
    }

    let port = port.ok_or("Backend did not print PORT: line".to_string())?;

    // Put stdout back for future reading (stderr messages)
    // (We already consumed it, but that's fine — we got what we needed)

    Ok((child, port))
}

/// Wait for the backend to be ready by polling its health endpoint.
fn wait_for_backend(port: u16, timeout_secs: u64) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{}", port);
    let start = std::time::Instant::now();
    loop {
        if start.elapsed() > Duration::from_secs(timeout_secs) {
            return Err(format!("Backend on port {} did not start within {}s", port, timeout_secs));
        }
        match reqwest::blocking::get(&url) {
            Ok(resp) if resp.status().is_success() => {
                eprintln!("[tauri] Backend ready on http://127.0.0.1:{}", port);
                return Ok(());
            }
            Ok(resp) => {
                eprintln!("[tauri] Backend returned {}, retrying...", resp.status());
            }
            Err(_) => {
                // Connection refused — backend still starting
            }
        }

        std::thread::sleep(Duration::from_millis(300));
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendState {
            process: Mutex::new(None),
            port: Mutex::new(None),
        })
        .setup(|app| {
            // Find and spawn the backend
            let binary_path = find_backend_binary()
                .ok_or_else(|| "fixate-backend binary not found. Run desktop/build-backend.sh first.".to_string())?;

            eprintln!("[tauri] Starting backend: {:?}", binary_path);

            let (child, port) = spawn_backend(&binary_path)
                .map_err(|e| format!("Backend start failed: {}", e))?;

            // Store state
            let state = app.state::<BackendState>();
            *state.process.lock().unwrap() = Some(child);
            *state.port.lock().unwrap() = Some(port);

            // Wait for backend to be ready
            wait_for_backend(port, 15)
                .map_err(|e| format!("Backend readiness failed: {}", e))?;

            // The webview window is auto-created by Tauri from tauri.conf.json
            // We just need to set the URL
            let window = app.get_webview_window("main")
                .ok_or("Main window not found")?;

            let url = format!("http://127.0.0.1:{}", port);
            window.eval(&format!("window.location.href = '{}';", url))
                .map_err(|e| format!("Failed to navigate: {}", e))?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                eprintln!("[tauri] Window destroyed — shutting down backend");

                let state = window.state::<BackendState>();
                let mut guard = state.process.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    eprintln!("[tauri] Killing backend process...");
                    let _ = child.kill();
                    let _ = child.wait();
                    eprintln!("[tauri] Backend process terminated.");
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Fixate desktop app");
}

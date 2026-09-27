//! AnyGameVoice desktop shell (Tauri).
//!
//! The Python FastAPI backend (`python app/main.py ui 8000`) owns all logic;
//! this shell only provides a native window and manages the backend process:
//! spawn on startup, kill on exit. In `tauri dev` the backend is started by
//! `beforeDevCommand`; here we also spawn it ourselves if port 8000 is free,
//! so double-clicking the built binary just works.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::process::{Child, Command};
use std::time::Duration;

const BACKEND_PORT: u16 = 8000;

fn backend_up() -> bool {
    TcpStream::connect_timeout(
        &format!("127.0.0.1:{BACKEND_PORT}").parse().unwrap(),
        Duration::from_millis(300),
    )
    .is_ok()
}

fn spawn_backend() -> Option<Child> {
    if backend_up() {
        return None; // `tauri dev` already started it via beforeDevCommand
    }
    // Repo root = two levels above the running binary in dev
    // (src-tauri/target/debug), one level in a bundled install.
    let candidates = [
        std::path::PathBuf::from("../../app/main.py"),
        std::path::PathBuf::from("../app/main.py"),
        std::path::PathBuf::from("app/main.py"),
    ];
    let script = candidates.iter().find(|p| p.is_file())?;
    let pythons = ["python", "python3", "py"];
    for py in pythons {
        if let Ok(child) = Command::new(py)
            .arg(script)
            .arg("ui")
            .arg(BACKEND_PORT.to_string())
            .spawn()
        {
            // Give FastAPI a moment to bind.
            for _ in 0..50 {
                if backend_up() {
                    return Some(child);
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            return Some(child);
        }
    }
    None
}

fn main() {
    let backend = std::sync::Mutex::new(spawn_backend());
    tauri::Builder::default()
        .build(tauri::generate_context!())
        .expect("failed to build AnyGameVoice shell")
        .run(move |_handle, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Ok(mut guard) = backend.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}

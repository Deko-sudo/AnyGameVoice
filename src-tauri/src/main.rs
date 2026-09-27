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

/// Triple-specific sidecar names produced by scripts/build_bundle.py.
const SIDECAR_NAMES: &[&str] = &[
    "anygamevoice-x86_64-pc-windows-msvc.exe",
    "anygamevoice-x86_64-unknown-linux-gnu",
    "anygamevoice-aarch64-unknown-linux-gnu",
    "anygamevoice-x86_64-apple-darwin",
    "anygamevoice-aarch64-apple-darwin",
];

fn backend_up() -> bool {
    TcpStream::connect_timeout(
        &format!("127.0.0.1:{BACKEND_PORT}").parse().unwrap(),
        Duration::from_millis(300),
    )
    .is_ok()
}

/// Native single-file bundle next to the app binary (Tauri externalBin).
fn sidecar_path() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    // Bundled layout: <dir>/binaries/<name>-<triple>[.exe], dev: <dir>/<name>.
    for sub in ["binaries", "."] {
        for name in SIDECAR_NAMES {
            let p = dir.join(sub).join(name);
            if p.is_file() {
                return Some(p);
            }
        }
    }
    None
}

fn spawn_backend() -> Option<Child> {
    if backend_up() {
        return None; // `tauri dev` already started it via beforeDevCommand
    }
    // 1) Native bundle sidecar (no Python needed).
    if let Some(bin) = sidecar_path() {
        if let Ok(child) = Command::new(&bin)
            .arg("ui")
            .arg(BACKEND_PORT.to_string())
            .spawn()
        {
            for _ in 0..50 {
                if backend_up() {
                    return Some(child);
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            return Some(child);
        }
    }
    // 2) Dev fallback: system Python running the repo backend.
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

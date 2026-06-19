use std::{
    env,
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Mutex, OnceLock},
    time::Duration,
};

use tauri::{path::BaseDirectory, Manager};

static STUDIO_API_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

fn studio_api_port() -> u16 {
    env::var("STUDIO_DESKTOP_API_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(8100)
}

fn studio_api_is_running() -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], studio_api_port()));
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

fn configured_api_launcher() -> Option<PathBuf> {
    env::var_os("ANIP_STUDIO_API_LAUNCHER")
        .map(PathBuf::from)
        .filter(|path| path.exists())
}

fn target_triple() -> &'static str {
    if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        "aarch64-apple-darwin"
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        "x86_64-apple-darwin"
    } else if cfg!(all(target_os = "windows", target_arch = "x86_64")) {
        "x86_64-pc-windows-msvc.exe"
    } else if cfg!(all(target_os = "linux", target_arch = "x86_64")) {
        "x86_64-unknown-linux-gnu"
    } else {
        ""
    }
}

fn bundled_api_launcher(app: &tauri::App) -> Option<PathBuf> {
    let triple = target_triple();
    if triple.is_empty() {
        return None;
    }
    app.path()
        .resolve(
            format!("bin/anip-studio-api-{triple}"),
            BaseDirectory::Resource,
        )
        .ok()
        .filter(|path| path.exists())
}

#[cfg(debug_assertions)]
fn development_api_launcher() -> Option<PathBuf> {
    let script = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../scripts/start-desktop-api.sh");
    script.exists().then_some(script)
}

#[cfg(not(debug_assertions))]
fn development_api_launcher() -> Option<PathBuf> {
    None
}

fn start_studio_api_if_configured(app: &tauri::App) {
    if env::var("ANIP_STUDIO_SKIP_API_LAUNCH").ok().as_deref() == Some("1") {
        return;
    }
    if studio_api_is_running() {
        return;
    }

    let Some(launcher) = configured_api_launcher()
        .or_else(|| bundled_api_launcher(app))
        .or_else(development_api_launcher)
    else {
        return;
    };

    let Ok(child) = Command::new(launcher)
        .env("STUDIO_MODE", "desktop")
        .env("STUDIO_DB_BACKEND", "sqlite")
        .env("STUDIO_SEED_SHOWCASES", "1")
        .env("STUDIO_READ_ONLY", "0")
        .env("STUDIO_RUN_MIGRATIONS", "1")
        .env("STUDIO_DESKTOP_API_PORT", studio_api_port().to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    else {
        return;
    };

    let child_slot = STUDIO_API_CHILD.get_or_init(|| Mutex::new(None));
    if let Ok(mut guard) = child_slot.lock() {
        *guard = Some(child);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            start_studio_api_if_configured(app);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run ANIP Studio desktop shell");
}

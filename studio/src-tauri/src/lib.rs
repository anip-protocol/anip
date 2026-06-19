use std::{
    env,
    fs::{self, OpenOptions},
    io::Write,
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

fn desktop_log_path() -> Option<PathBuf> {
    let home = env::var_os("HOME").map(PathBuf::from)?;
    Some(home.join("Library").join("Logs").join("ANIP Studio").join("desktop-api.log"))
}

fn append_desktop_log(message: &str) {
    let Some(path) = desktop_log_path() else {
        return;
    };
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{message}");
    }
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

fn macos_bundle_api_launcher() -> Option<PathBuf> {
    let triple = target_triple();
    if triple.is_empty() {
        return None;
    }
    let executable = env::current_exe().ok()?;
    let contents_dir = executable.parent()?.parent()?;
    let candidate = contents_dir
        .join("Resources")
        .join("bin")
        .join(format!("anip-studio-api-{triple}"));
    candidate.exists().then_some(candidate)
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
        append_desktop_log("Studio API launch skipped by ANIP_STUDIO_SKIP_API_LAUNCH=1");
        return;
    }
    if studio_api_is_running() {
        append_desktop_log("Studio API already running on configured desktop port");
        return;
    }

    let Some(launcher) = configured_api_launcher()
        .or_else(|| bundled_api_launcher(app))
        .or_else(macos_bundle_api_launcher)
        .or_else(development_api_launcher)
    else {
        append_desktop_log("No Studio API launcher found");
        return;
    };

    append_desktop_log(&format!("Launching Studio API sidecar: {}", launcher.display()));
    let log_file = desktop_log_path().and_then(|path| {
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        OpenOptions::new().create(true).append(true).open(path).ok()
    });
    let stdout = log_file
        .as_ref()
        .and_then(|file| file.try_clone().ok())
        .map(Stdio::from)
        .unwrap_or_else(Stdio::null);
    let stderr = log_file
        .map(Stdio::from)
        .unwrap_or_else(Stdio::null);

    let Ok(child) = Command::new(&launcher)
        .env("STUDIO_MODE", "desktop")
        .env("STUDIO_DB_BACKEND", "sqlite")
        .env("STUDIO_SEED_SHOWCASES", "1")
        .env("STUDIO_READ_ONLY", "0")
        .env("STUDIO_RUN_MIGRATIONS", "1")
        .env("STUDIO_DESKTOP_API_PORT", studio_api_port().to_string())
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr)
        .spawn()
    else {
        append_desktop_log(&format!("Failed to spawn Studio API sidecar: {}", launcher.display()));
        return;
    };

    append_desktop_log("Studio API sidecar process spawned");

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

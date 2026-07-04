use std::{
    env,
    fs::{self, OpenOptions},
    io::Write,
    net::{SocketAddr, TcpListener, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Mutex, OnceLock},
    time::Duration,
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;
use tauri::{path::BaseDirectory, webview::PageLoadEvent, Manager};

static STUDIO_API_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();
static STUDIO_API_PORT: OnceLock<u16> = OnceLock::new();
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const ALLOWED_EXTERNAL_URLS: &[&str] = &["https://anip.dev", "https://anip.dev/"];

fn configured_studio_api_port() -> Option<u16> {
    env::var("STUDIO_DESKTOP_API_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
}

fn allocate_studio_api_port() -> u16 {
    if let Some(port) = configured_studio_api_port() {
        return port;
    }

    TcpListener::bind(SocketAddr::from(([127, 0, 0, 1], 0)))
        .ok()
        .and_then(|listener| listener.local_addr().ok())
        .map(|addr| addr.port())
        .unwrap_or(8100)
}

fn studio_api_port() -> u16 {
    *STUDIO_API_PORT.get_or_init(allocate_studio_api_port)
}

fn studio_api_base() -> String {
    format!("http://127.0.0.1:{}", studio_api_port())
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
    Some(
        home.join("Library")
            .join("Logs")
            .join("ANIP Studio")
            .join("desktop-api.log"),
    )
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

fn stop_studio_api_sidecar() {
    let Some(child_slot) = STUDIO_API_CHILD.get() else {
        return;
    };
    let Ok(mut guard) = child_slot.lock() else {
        return;
    };
    let Some(mut child) = guard.take() else {
        return;
    };

    append_desktop_log("Stopping Studio API sidecar process");
    let _ = child.kill();
    let _ = child.wait();
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
        append_desktop_log(&format!(
            "Studio API already running on {}",
            studio_api_base()
        ));
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

    append_desktop_log(&format!(
        "Launching Studio API sidecar on {}: {}",
        studio_api_base(),
        launcher.display()
    ));
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
    let stderr = log_file.map(Stdio::from).unwrap_or_else(Stdio::null);

    let mut command = Command::new(&launcher);
    command
        .env("STUDIO_MODE", "desktop")
        .env("STUDIO_DB_BACKEND", "sqlite")
        .env("STUDIO_SEED_SHOWCASES", "1")
        .env("STUDIO_READ_ONLY", "0")
        .env("STUDIO_RUN_MIGRATIONS", "1")
        .env("STUDIO_DESKTOP_API_PORT", studio_api_port().to_string())
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr);

    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    let Ok(child) = command.spawn() else {
        append_desktop_log(&format!(
            "Failed to spawn Studio API sidecar: {}",
            launcher.display()
        ));
        return;
    };

    append_desktop_log("Studio API sidecar process spawned");

    let child_slot = STUDIO_API_CHILD.get_or_init(|| Mutex::new(None));
    if let Ok(mut guard) = child_slot.lock() {
        *guard = Some(child);
    }
}

#[tauri::command]
fn studio_api_base_url() -> String {
    studio_api_base()
}

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    if !ALLOWED_EXTERNAL_URLS.contains(&url.as_str()) {
        return Err("external URL is not allowed".to_string());
    }

    #[cfg(target_os = "macos")]
    let status = Command::new("open").arg(&url).status();

    #[cfg(target_os = "windows")]
    let status = Command::new("cmd").args(["/C", "start", "", &url]).status();

    #[cfg(all(unix, not(target_os = "macos")))]
    let status = Command::new("xdg-open").arg(&url).status();

    status
        .map_err(|err| format!("failed to open external URL: {err}"))
        .and_then(|status| {
            if status.success() {
                Ok(())
            } else {
                Err(format!("failed to open external URL: status {status}"))
            }
        })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            open_external_url,
            studio_api_base_url
        ])
        .on_page_load(|webview, payload| {
            if webview.label() != "main" || payload.event() != PageLoadEvent::Finished {
                return;
            }

            if let Some(main) = webview.get_webview_window("main") {
                let _ = main.show();
                let _ = main.set_focus();
            }
            if let Some(splashscreen) = webview.get_webview_window("splashscreen") {
                let _ = splashscreen.close();
            }
        })
        .setup(|app| {
            start_studio_api_if_configured(app);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build ANIP Studio desktop shell");

    app.run(|_app_handle, event| {
        if matches!(
            event,
            tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
        ) {
            stop_studio_api_sidecar();
        }
    });
}

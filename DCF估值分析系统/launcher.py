import os, sys, subprocess, socket, webbrowser, time

def find_free_port(start=8513, end=8525):
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    return 0

def find_python():
    for cmd in ['python', 'py -3']:
        try:
            subprocess.run(cmd.split() + ['--version'], check=True, capture_output=True)
            return cmd
        except Exception:
            continue
    return None

def main():
    python = find_python()
    if not python:
        print("ERROR: Python not found.")
        input("Press Enter to exit...")
        return

    required_packages = ['streamlit', 'pandas', 'numpy', 'matplotlib', 'akshare']
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"Installing missing packages: {', '.join(missing)}...")
        subprocess.run(python.split() + ['-m', 'pip', 'install'] + missing)

    port = find_free_port()
    if port == 0:
        print("ERROR: No free port found between 8513-8525.")
        input("Press Enter to exit...")
        return

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 45)
    print("    DCF Valuation Analysis System")
    print("=" * 45)
    print(f"    URL: http://localhost:{port}")
    print()

    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"

    print("Starting server...")
    proc = subprocess.Popen(
        python.split() + ['-m', 'streamlit', 'run', 'streamlit_app.py',
                          f'--server.port={port}', '--server.headless=true',
                          '--server.address=0.0.0.0'],
        env=env
    )

    time.sleep(3)
    webbrowser.open(f"http://localhost:{port}", new=2)

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

    print()
    print("Server stopped.")
    input("Press Enter to exit...")

if __name__ == '__main__':
    main()

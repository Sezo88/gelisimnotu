"""
E-Okul Gelişim Düzeyleri Girişi - Başlatıcı
Uvicorn sunucusunu başlatır ve varsayılan tarayıcıda UI'ı açar.
"""

import webbrowser
import threading
import time
import uvicorn

PORT = 8585

def open_browser():
    """Wait for the server to start, then open the browser."""
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")

if __name__ == "__main__":
    print("=" * 50)
    print("  E-Okul Gelişim Düzeyleri Girişi")
    print("  Toplu Kazanım Otomasyon Aracı")
    print(f"  http://localhost:{PORT}")
    print("=" * 50)

    # Open browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run("gelisim_app:app", host="127.0.0.1", port=PORT, reload=False)

"""Atualiza a arte "Tempo de código" do README com os dados públicos do WakaTime.

    python -P wakatime/gerar.py

Baixa o perfil público (sem chave de API) para dados.js e renderiza arte.html num Chromium headless em 2x, nas versões
escura (assets/wakatime.png) e clara (assets/wakatime-claro.png). A Action .github/workflows/wakatime.yml roda toda
semana. O navegador vem de NAVEGADOR; sem ela, usa o Chrome do Linux ou o Edge do Windows.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

AQUI = Path(__file__).resolve().parent
ASSETS = AQUI.parent / "assets"
USUARIO = "YuriLRodrigues"
API = "https://wakatime.com/api/v1"
LARGURA, ALTURA, RAIO, ESCALA = 880, 300, 16, 2
BORDA = {False: (255, 255, 255, 26), True: (9, 9, 11, 30)}


def buscar(caminho: str) -> dict:
    pedido = urllib.request.Request(f"{API}{caminho}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return json.load(resposta)["data"]


def baixar_dados() -> None:
    perfil = buscar(f"/users/@{USUARIO}")
    stats = buscar(f"/users/@{USUARIO}/stats/all_time")
    dias = buscar(f"/users/{perfil['id']}/insights/days/public")["days"]
    if not stats.get("total_seconds") or len(dias) < 300:
        sys.exit("O WakaTime ainda está calculando as estatísticas; as imagens ficam como estão.")
    dados = {
        "atualizado": date.today().isoformat(),
        "desde": perfil["created_at"][:10],
        "totalSegundos": round(stats["total_seconds"]),
        "mediaSegundos": round(stats["daily_average"]),
        "diasComCodigo": stats["days_minus_holidays"],
        "linguagens": [
            {"nome": l["name"], "segundos": round(l["total_seconds"]), "pct": l["percent"]} for l in stats["languages"][:6]
        ],
        # O perfil público entrega cada dia numa faixa: 0, até 3 h, até 8 h, até 10 h, até 12 h e mais de 12 h.
        "dias": [[d["date"], d["total"]] for d in dias],
    }
    (AQUI / "dados.js").write_text("window.WAKA = " + json.dumps(dados) + ";\n", encoding="utf-8")
    print(f"dados: {dados['totalSegundos'] // 3600} h desde {dados['desde']}, {len(dias)} dias no mapa")


def navegador() -> str:
    if os.environ.get("NAVEGADOR"):
        return os.environ["NAVEGADOR"]
    if sys.platform == "win32":
        return r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    for nome in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if caminho := shutil.which(nome):
            return caminho
    sys.exit("Nenhum Chrome/Chromium encontrado; defina NAVEGADOR.")


def renderizar(destino: Path, claro: bool) -> None:
    destino.unlink(missing_ok=True)
    url = (AQUI / "arte.html").as_uri() + ("?claro" if claro else "")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as perfil:
        argumentos = [
            navegador(), "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            f"--user-data-dir={perfil}", f"--force-device-scale-factor={ESCALA}",
            f"--window-size={LARGURA},{ALTURA}", "--virtual-time-budget=7000",
            "--allow-file-access-from-files", f"--screenshot={destino}", url,
        ]
        if sys.platform != "win32":
            # Os runners do GitHub não permitem o sandbox do Chrome; a página é só o arquivo local.
            argumentos.insert(1, "--no-sandbox")
        subprocess.run(argumentos, timeout=120, capture_output=True)
        limite = time.time() + 60
        while time.time() < limite and not (destino.exists() and destino.stat().st_size > 0):
            time.sleep(0.5)
    if not destino.exists():
        sys.exit(f"O navegador não gerou {destino.name}.")


def arredondar(caminho: Path, claro: bool) -> None:
    """Cantos transparentes e uma borda de 1px na cor do tema, como as outras imagens do README."""
    im = Image.open(caminho).convert("RGBA")
    f = 4  # máscara e borda em 4x para sair suave
    tam = (im.width * f, im.height * f)
    r = RAIO * ESCALA * f
    mascara = Image.new("L", tam, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, tam[0] - 1, tam[1] - 1), radius=r, fill=255)
    im.putalpha(mascara.resize(im.size, Image.LANCZOS))
    contorno = Image.new("RGBA", tam, (0, 0, 0, 0))
    ImageDraw.Draw(contorno).rounded_rectangle(
        (0, 0, tam[0] - 1, tam[1] - 1), radius=r, outline=BORDA[claro], width=ESCALA * f
    )
    Image.alpha_composite(im, contorno.resize(im.size, Image.LANCZOS)).save(caminho, optimize=True)


def main() -> None:
    baixar_dados()
    for nome, claro in (("wakatime.png", False), ("wakatime-claro.png", True)):
        destino = ASSETS / nome
        renderizar(destino, claro)
        arredondar(destino, claro)
        print(f"ok: {nome} {Image.open(destino).size} {destino.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()

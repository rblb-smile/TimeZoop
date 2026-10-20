# PyInstaller 설정: python -m PyInstaller packaging/TimeZoop.spec --noconfirm
# 결과: dist/TimeZoop/TimeZoop.exe (폴더째 배포, 설치 파일은 installer.iss)
# 보통은 packaging/build.ps1 로 빌드한다 (vendor 복사, 개인정보 검사, 설치 파일까지).
#
# 넣는 것: 프로그램 코드, 화면(web), cuBLAS 12(음성 인식용)
# 빌드 뒤 build.ps1이 복사하는 것: vendor/llama.cpp, vendor/ffmpeg
#   (여기 datas로 넣으면 PyInstaller가 그 DLL들을 분석해 최상위에 한 벌 더 복사해서 540MB가 늘어난다)
# 넣지 않는 것: data/(분석 데이터), models/(AI 모델: 첫 실행 때 받음), scripts/, 설정·로그인 정보,
#   cuDNN·NVRTC(ctranslate2가 쓰지 않음, 실제 분석으로 확인), PyAV(대신 rthook_av.py가 자리 채움), Pillow(로고 만들 때만 씀)

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
SITE = ROOT / ".venv" / "Lib" / "site-packages"

datas = [(str(ROOT / "soop_timeline" / "web"), "soop_timeline/web")]
datas += collect_data_files("faster_whisper")  # 음성 구간 찾기(VAD) 모델 파일

# faster-whisper(ctranslate2)가 쓰는 CUDA 12 cuBLAS: stt._add_cuda_dlls가 nvidia/*/bin을 찾는다
datas += [(str(p), "nvidia/cublas/bin") for p in (SITE / "nvidia" / "cublas" / "bin").glob("*.dll")]

binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["soop_timeline", "clr"],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "PIL", "av"],
    runtime_hooks=[str(ROOT / "packaging" / "rthook_av.py")],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TimeZoop",
    icon=str(ROOT / "soop_timeline" / "web" / "app.ico"),
    console=False,  # 검은 콘솔 창 없이
    version=str(ROOT / "packaging" / "version.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="TimeZoop")

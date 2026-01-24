#!/usr/bin/env python3
"""
Runtime Verification Tool for Global Export Intelligence Platform

백엔드 기동 → /health 확인 → API 호출 → 종료 자동화

Usage:
    python tools/runtime_verify.py

Requirements:
    pip install requests
"""

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests


@dataclass
class RuntimeVerifyConfig:
    """런타임 검증 설정"""
    # 프로젝트 루트 (backend 폴더의 상위)
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    host: str = "127.0.0.1"
    port: int = 8000
    startup_timeout_sec: int = 30
    request_timeout_sec: int = 30  # KOTRA API 호출이 포함되므로 넉넉하게 설정
    
    # 환경 변수
    kotra_service_key: str = "83b96790de580e57527e049d59bfcb18ae34d2bfe646c11a5d2ee6b3d95e9b23"


def _is_windows() -> bool:
    return os.name == "nt"


def _kill_process_tree(proc: subprocess.Popen):
    """
    프로세스 트리 종료
    - Windows: taskkill /T /F
    - Unix: SIGTERM → SIGKILL
    """
    if proc.poll() is not None:
        return

    try:
        if _is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _wait_for_health(base_url: str, timeout_sec: int, req_timeout: int) -> Dict[str, Any]:
    """
    /health 엔드포인트가 응답할 때까지 대기
    """
    deadline = time.time() + timeout_sec
    last_err: Optional[str] = None

    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=req_timeout)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") in ("ok", "healthy"):
                    return data
                last_err = f"Unexpected health payload: {data}"
            else:
                last_err = f"Health status_code={r.status_code}, body={r.text[:200]}"
        except requests.exceptions.ConnectionError:
            last_err = "Connection refused (server starting...)"
        except Exception as e:
            last_err = str(e)

        time.sleep(0.5)

    raise RuntimeError(f"Backend did not become healthy within {timeout_sec}s. Last error: {last_err}")


def _test_simulate_api(base_url: str, timeout: int) -> Dict[str, Any]:
    """
    /simulate/quick API 테스트 (성과 시뮬레이션)
    """
    params = {
        "hs_code": "330499",
        "country": "US",
        "price": 10,
        "moq": 1000,
        "capacity": 50000
    }
    
    r = requests.get(
        f"{base_url}/simulate/quick",
        params=params,
        timeout=timeout
    )
    
    if r.status_code != 200:
        raise RuntimeError(f"/simulate/quick failed: status={r.status_code}, body={r.text[:300]}")
    
    data = r.json()
    
    # 필수 필드 검증
    required_keys = {
        "target_country", "hs_code", "success_probability",
        "market_size", "estimated_revenue_min", "estimated_revenue_max"
    }
    missing = required_keys - set(data.keys())
    if missing:
        raise RuntimeError(f"/simulate/quick response missing keys: {missing}")
    
    # 값 유효성 검증
    if data["success_probability"] < 0 or data["success_probability"] > 1:
        raise RuntimeError(f"Invalid success_probability: {data['success_probability']}")
    
    if data["market_size"] <= 0:
        raise RuntimeError(f"Invalid market_size: {data['market_size']}")
    
    return data


def _test_match_api(base_url: str, timeout: int) -> Dict[str, Any]:
    """
    /match/seller API 테스트 (바이어 매칭)
    """
    params = {
        "hs_code": "330499",
        "country": "KR",
        "price_min": 5,
        "price_max": 8,
        "moq": 1000,
        "certifications": "FDA,ISO",
        "top_n": 5
    }
    
    r = requests.post(
        f"{base_url}/match/seller",
        params=params,
        timeout=timeout
    )
    
    if r.status_code != 200:
        raise RuntimeError(f"/match/seller failed: status={r.status_code}, body={r.text[:300]}")
    
    data = r.json()
    
    # 필수 필드 검증
    required_keys = {"total_candidates", "matches", "data_sources"}
    missing = required_keys - set(data.keys())
    if missing:
        raise RuntimeError(f"/match/seller response missing keys: {missing}")
    
    # 매칭 결과 검증
    if not isinstance(data["matches"], list):
        raise RuntimeError(f"matches should be a list, got: {type(data['matches'])}")
    
    if len(data["matches"]) > 0:
        match = data["matches"][0]
        match_required = {"partner_id", "fit_score", "country"}
        match_missing = match_required - set(match.keys())
        if match_missing:
            raise RuntimeError(f"Match item missing keys: {match_missing}")
    
    return data


def _test_recommend_api(base_url: str, timeout: int) -> Dict[str, Any]:
    """
    /recommend/quick API 테스트 (국가 추천)
    """
    params = {
        "hs_code": "330499",
        "top_n": 5
    }
    
    r = requests.get(
        f"{base_url}/recommend/quick",
        params=params,
        timeout=timeout
    )
    
    if r.status_code != 200:
        raise RuntimeError(f"/recommend/quick failed: status={r.status_code}, body={r.text[:300]}")
    
    data = r.json()
    
    # 필수 필드 검증
    required_keys = {"hs_code", "recommendations", "data_sources"}
    missing = required_keys - set(data.keys())
    if missing:
        raise RuntimeError(f"/recommend/quick response missing keys: {missing}")
    
    return data


def run_runtime_verify(cfg: RuntimeVerifyConfig) -> None:
    """
    런타임 검증 실행
    
    1. 백엔드 서버 시작
    2. /health 확인
    3. 주요 API 호출 테스트
    4. 서버 종료
    """
    project_root = cfg.project_root.resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"project_root not found: {project_root}")
    
    base_url = f"http://{cfg.host}:{cfg.port}"
    
    print(f"🚀 Runtime Verification Starting...")
    print(f"   Project: {project_root}")
    print(f"   URL: {base_url}")
    print()
    
    # 환경 변수 설정
    env = os.environ.copy()
    env["KOTRA_SERVICE_KEY"] = cfg.kotra_service_key
    env["HOST"] = cfg.host
    env["PORT"] = str(cfg.port)
    
    # 프로세스 생성 옵션
    creationflags = 0
    preexec_fn = None
    if _is_windows():
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        preexec_fn = os.setsid
    
    # 1) 백엔드 서버 시작
    print("📦 Starting backend server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", 
         "--host", cfg.host, "--port", str(cfg.port)],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        creationflags=creationflags,
        preexec_fn=preexec_fn,
    )
    
    try:
        # 2) /health 확인
        print("⏳ Waiting for /health endpoint...")
        health_data = _wait_for_health(base_url, cfg.startup_timeout_sec, cfg.request_timeout_sec)
        print(f"✅ /health OK: {health_data.get('status')}")
        
        services = health_data.get("services", {})
        for svc, status in services.items():
            emoji = "✅" if status in ("available", "configured") else "⚠️"
            print(f"   {emoji} {svc}: {status}")
        print()
        
        # 3) API 테스트
        print("🧪 Testing APIs...")
        
        # 3-1) Simulate API
        print("   Testing /simulate/quick...")
        sim_data = _test_simulate_api(base_url, cfg.request_timeout_sec)
        print(f"   ✅ /simulate/quick OK")
        print(f"      - Country: {sim_data['target_country']}")
        print(f"      - Success Probability: {sim_data['success_probability']*100:.1f}%")
        print(f"      - Market Size: ${sim_data['market_size']:,.0f}")
        print()
        
        # 3-2) Match API
        print("   Testing /match/seller...")
        match_data = _test_match_api(base_url, cfg.request_timeout_sec)
        print(f"   ✅ /match/seller OK")
        print(f"      - Total Candidates: {match_data['total_candidates']}")
        print(f"      - Matches Returned: {len(match_data['matches'])}")
        print()
        
        # 3-3) Recommend API
        print("   Testing /recommend/quick...")
        rec_data = _test_recommend_api(base_url, cfg.request_timeout_sec)
        print(f"   ✅ /recommend/quick OK")
        print(f"      - Recommendations: {len(rec_data.get('recommendations', []))}")
        print()
        
        print("=" * 50)
        print("✅ Runtime verification PASSED")
        print("=" * 50)
        print()
        print("Summary:")
        print(f"  - /health: OK")
        print(f"  - /simulate/quick: OK (probability={sim_data['success_probability']*100:.1f}%)")
        print(f"  - /match/seller: OK (candidates={match_data['total_candidates']})")
        print(f"  - /recommend/quick: OK")
        
    except Exception as e:
        print()
        print("=" * 50)
        print(f"❌ Runtime verification FAILED: {e}")
        print("=" * 50)
        raise
        
    finally:
        # 4) 서버 종료
        print()
        print("🛑 Stopping backend server...")
        _kill_process_tree(proc)
        
        # 디버깅용 로그 출력 (실패 시)
        if proc.stdout:
            try:
                out = proc.stdout.read()
                if out and "FAILED" in str(sys.exc_info()[1] or ""):
                    print("\n--- Backend Logs (tail) ---")
                    tail = "\n".join(out.strip().splitlines()[-30:])
                    print(tail)
            except Exception:
                pass
        
        print("✅ Server stopped")


def main():
    """CLI 진입점"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Runtime Verification Tool")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--timeout", type=int, default=30, help="Startup timeout (seconds)")
    
    args = parser.parse_args()
    
    cfg = RuntimeVerifyConfig(
        host=args.host,
        port=args.port,
        startup_timeout_sec=args.timeout,
    )
    
    try:
        run_runtime_verify(cfg)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

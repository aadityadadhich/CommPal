import asyncio
import math
import os
import shutil
import subprocess
import wave
from pathlib import Path
from typing import List, Dict, Any

import edge_tts
import imageio_ffmpeg
from playwright.async_api import async_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT_DIR / "video_build"
OUTPUT_MP4 = ROOT_DIR / "commpal_demo.mp4"
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "en-US-AndrewNeural"
FPS = 12  # 12 fps deterministic frame capture -> smooth 24fps interpolated output

SCENES: List[Dict[str, Any]] = [
    {
        "id": "scene1_intro",
        "title": "Autonomous Agentic Commerce",
        "narration": (
            "Meet CommPal: Autonomous Agentic Commerce and Multi-Store Aggregation, built for the PayPal A.I. Hackathon. "
            "Today's A.I. assistants can recommend products, but trusting an A.I. with your primary bank card is risky. "
            "CommPal solves this with a sandboxed PayPal e-wallet and a deterministic nine-rule spending mandate."
        ),
        "caption": "CommPal — Autonomous Agentic Commerce & Multi-Store Aggregation powered by PayPal Sandbox",
    },
    {
        "id": "scene2_arch",
        "title": "8-Step Guardrailed Pipeline",
        "narration": (
            "Every autonomous purchase flows through an eight-step guardrailed pipeline. "
            "CommPal queries five merchants in parallel—Quick10, ZipBasket, CornerStore, MegaMart, and BulkBarn—scores offers "
            "by urgency, price, and reliability, verifies your spending mandate, and settles funds through PayPal Sandbox."
        ),
        "caption": "8-Step Pipeline: Intent -> 5-Store Aggregation -> SLA Scoring -> 9-Rule Mandate -> PayPal Escrow & Capture",
    },
    {
        "id": "scene3_recipe",
        "title": "AI Assistant: Recipe Decomposition",
        "narration": (
            "Let's see the live CommPal workspace in action. When we tell the A.I. assistant, "
            "'I need to make paneer butter masala, order all ingredients', CommPal thinks step by step. "
            "It decomposes the recipe into five ingredients, checks My Pantry to skip items already in stock, "
            "selects the best store for each item, and completes five PayPal Sandbox orders automatically."
        ),
        "caption": "Live Demo: 'I need to make paneer butter masala, order all ingredients' -> AI Reasoning + 5 PayPal Orders",
    },
    {
        "id": "scene4_pantry_why",
        "title": "Auto-Restock & Explainable Routing",
        "narration": (
            "In My Pantry on the left, clicking 'Ran Out' on A4 Copy Paper immediately triggers an urgent quick-commerce restock. "
            "Clicking 'Why this store?' on any order opens the transparent score breakdown across all five stores, "
            "showing why Quick10 won on delivery speed and utility."
        ),
        "caption": "1-Click Depletion Auto-Buy & Transparent Multi-Merchant Utility Score Breakdown",
    },
    {
        "id": "scene5_approval",
        "title": "Mandate Safety Gate: Human Approval",
        "narration": (
            "What if someone asks to buy an untracked item like W.D. Forty? "
            "Mandate Rule Six automatically pauses execution and flags the order for human permission. "
            "With one click on 'Approve and Pay with PayPal', the reserved funds are captured and the order is dispatched."
        ),
        "caption": "Deterministic Safety Gate: Untracked items pause for 1-click Human Approval before PayPal capture",
    },
    {
        "id": "scene6_audit_outro",
        "title": "Kill Switch & SHA-256 Audit Chain",
        "narration": (
            "Every action, policy verdict, and PayPal receipt is sealed in a tamper-evident S.H.A. 256 cryptographic hash chain, "
            "and an emergency Kill Switch can freeze the agent at any time. "
            "CommPal: Safe, explainable, autonomous shopping powered by PayPal."
        ),
        "caption": "Tamper-Evident SHA-256 Cryptographic Audit Log & Emergency Kill Switch",
    },
]


def get_audio_duration(audio_path: Path) -> float:
    """Use ffmpeg to probe exact duration of generated mp3/wav."""
    wav_path = audio_path.with_suffix(".wav")
    subprocess.run(
        [FFMPEG_EXE, "-y", "-i", str(audio_path), "-ar", "24000", "-ac", "1", str(wav_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


async def generate_all_voiceovers():
    print("1/4 Generating Microsoft Neural TTS voiceovers (edge-tts)...")
    for sc in SCENES:
        mp3_path = BUILD_DIR / f"{sc['id']}.mp3"
        communicate = edge_tts.Communicate(sc["narration"], VOICE, rate="+4%")
        await communicate.save(str(mp3_path))
        dur = get_audio_duration(mp3_path)
        sc["duration"] = round(dur + 0.6, 2)  # Add 0.6s breathing room per scene
        print(f"  - {sc['id']}: {sc['duration']:.2f}s")


OVERLAY_SETUP_JS = """
() => {
  if (document.getElementById('demo-overlay-root')) return;
  const style = document.createElement('style');
  style.textContent = `
    #demo-cursor {
      position: fixed;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: rgba(56, 189, 248, 0.35);
      border: 3px solid #38bdf8;
      box-shadow: 0 0 20px rgba(56, 189, 248, 0.9);
      pointer-events: none;
      z-index: 99999;
      transform: translate(-50%, -50%);
      transition: left 0.45s cubic-bezier(0.22, 1, 0.36, 1), top 0.45s cubic-bezier(0.22, 1, 0.36, 1), transform 0.15s ease;
    }
    #demo-cursor::after {
      content: '';
      position: absolute;
      left: 50%;
      top: 50%;
      width: 8px;
      height: 8px;
      background: #ffffff;
      border-radius: 50%;
      transform: translate(-50%, -50%);
    }
    #demo-cursor.clicking {
      transform: translate(-50%, -50%) scale(0.7);
      background: rgba(16, 185, 129, 0.6);
      border-color: #10b981;
    }
    #demo-caption-bar {
      position: fixed;
      bottom: 22px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(9, 11, 16, 0.92);
      border: 1px solid rgba(56, 189, 248, 0.45);
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.75);
      padding: 12px 26px;
      border-radius: 999px;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
      font-size: 17px;
      font-weight: 600;
      z-index: 99990;
      display: flex;
      align-items: center;
      gap: 12px;
      white-space: nowrap;
    }
    #demo-scene-tag {
      background: #0070ba;
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      padding: 4px 10px;
      border-radius: 999px;
      letter-spacing: 0.05em;
    }
    #demo-slide-modal {
      position: fixed;
      inset: 0;
      background: radial-gradient(circle at 20% 20%, #0f2942 0%, #090b10 65%);
      z-index: 99980;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 60px;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
      transition: opacity 0.4s ease;
    }
    .slide-card-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 24px;
      max-width: 1320px;
      width: 100%;
      margin-top: 40px;
    }
    .slide-box {
      background: rgba(19, 23, 34, 0.9);
      border: 1px solid #2b3548;
      border-top: 4px solid #0070ba;
      border-radius: 14px;
      padding: 28px;
      box-shadow: 0 18px 40px rgba(0,0,0,0.45);
    }
    .pipeline-row {
      display: flex;
      align-items: center;
      gap: 14px;
      max-width: 1440px;
      margin-top: 42px;
      flex-wrap: wrap;
      justify-content: center;
    }
    .pipe-step {
      background: rgba(19, 23, 34, 0.95);
      border: 2px solid #2b3548;
      border-radius: 12px;
      padding: 20px 22px;
      width: 240px;
      text-align: center;
      transition: all 0.25s ease;
    }
    .pipe-step.active {
      border-color: #38bdf8;
      background: rgba(0, 112, 186, 0.22);
      transform: translateY(-6px);
      box-shadow: 0 12px 28px rgba(0, 112, 186, 0.35);
    }
  `;
  document.head.appendChild(style);

  const root = document.createElement('div');
  root.id = 'demo-overlay-root';
  root.innerHTML = `
    <div id="demo-cursor" style="left:960px; top:540px;"></div>
    <div id="demo-caption-bar">
      <span id="demo-scene-tag">COMMPAL DEMO</span>
      <span id="demo-caption-text">Initializing...</span>
    </div>
    <div id="demo-slide-modal" style="display:none;"></div>
  `;
  document.body.appendChild(root);
}
"""


async def record_frames_for_scene(page, scene: Dict[str, Any], action_Timeline_fn) -> Path:
    """Capture deterministic PNG frames at FPS for the exact duration of the scene and encode MP4."""
    sc_id = scene["id"]
    dur = scene["duration"]
    total_frames = max(1, int(math.ceil(dur * FPS)))
    frames_dir = BUILD_DIR / f"frames_{sc_id}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    await page.evaluate(
        """([tag, cap]) => {
            const t = document.getElementById('demo-scene-tag');
            const c = document.getElementById('demo-caption-text');
            if (t) t.textContent = tag;
            if (c) c.textContent = cap;
        }""",
        [scene["title"], scene["caption"]],
    )

    for f_idx in range(total_frames):
        progress = f_idx / float(max(1, total_frames - 1))
        elapsed = f_idx / float(FPS)
        await action_Timeline_fn(page, f_idx, elapsed, progress)
        frame_file = frames_dir / f"frame_{f_idx:04d}.png"
        await page.screenshot(path=str(frame_file), type="png")

    # Combine frames + scene audio into a scene MP4
    scene_mp4 = BUILD_DIR / f"{sc_id}.mp4"
    audio_wav = BUILD_DIR / f"{sc_id}.wav"
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-i",
        str(audio_wav),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-r",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(scene_mp4),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return scene_mp4


async def build_video():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate neural TTS voiceovers and measure exact scene durations
    await generate_all_voiceovers()
    total_dur = sum(s["duration"] for s in SCENES)
    print(f"Total planned video duration: {total_dur:.1f} seconds (< 120s limit)")

    # 2. Reset backend demo state before recording
    import httpx
    httpx.post("http://127.0.0.1:8000/api/demo/reset", timeout=10.0)

    print("2/4 Launching 1920x1080 headless browser & recording animated scenes...")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page = await context.new_page()
        await page.goto("http://127.0.0.1:3000", wait_until="networkidle")
        await page.evaluate(OVERLAY_SETUP_JS)

        scene_videos: List[Path] = []

        # --- SCENE 1: Animated Intro Slide ---
        async def s1_timeline(pg, f_idx, elapsed, progress):
            if f_idx == 0:
                await pg.evaluate(
                    """() => {
                        const m = document.getElementById('demo-slide-modal');
                        m.style.display = 'flex';
                        m.style.opacity = '1';
                        m.innerHTML = `
                          <div style="display:flex; align-items:center; gap:18px; margin-bottom:18px;">
                            <div style="width:68px; height:68px; border-radius:16px; background:#0070ba; display:flex; align-items:center; justify-content:center; font-size:30px; font-weight:800; box-shadow:0 0 35px rgba(0,112,186,0.7);">CP</div>
                            <div>
                              <div style="font-size:14px; font-weight:700; color:#38bdf8; letter-spacing:0.12em; text-transform:uppercase;">PayPal AI Hackathon Submission</div>
                              <div style="font-size:48px; font-weight:800; letter-spacing:-0.02em;">CommPal — Autonomous Agentic Commerce</div>
                            </div>
                          </div>
                          <p style="font-size:22px; color:#94a3b8; max-width:980px; text-align:center; line-height:1.5;">
                            An AI shopping &amp; inventory agent that thinks, compares 5 stores, and buys on your behalf—safely isolated inside a <strong>Sandboxed PayPal E-Wallet</strong>.
                          </p>
                          <div class="slide-card-grid">
                            <div class="slide-box" id="s1-b1" style="opacity:0.25; transform:translateY(15px); transition:all 0.4s;">
                              <div style="font-size:13px; color:#38bdf8; font-weight:700; text-transform:uppercase;">1. Isolated Financial Risk</div>
                              <div style="font-size:22px; font-weight:700; margin:10px 0;">3-Bucket PayPal Escrow</div>
                              <div style="font-size:15px; color:#94a3b8; line-height:1.5;">Separates <code>Available</code>, <code>Held in Escrow</code>, and <code>Settled Spend</code> so the AI never touches your primary bank card.</div>
                            </div>
                            <div class="slide-box" id="s1-b2" style="opacity:0.25; transform:translateY(15px); transition:all 0.4s; border-top-color:#10b981;">
                              <div style="font-size:13px; color:#10b981; font-weight:700; text-transform:uppercase;">2. Deterministic Governance</div>
                              <div style="font-size:22px; font-weight:700; margin:10px 0;">9-Rule Spending Mandate</div>
                              <div style="font-size:15px; color:#94a3b8; line-height:1.5;">Enforces per-order caps ($25 auto-approve), daily/monthly limits ($80/day), anomaly guards, and an instant Kill Switch.</div>
                            </div>
                            <div class="slide-box" id="s1-b3" style="opacity:0.25; transform:translateY(15px); transition:all 0.4s; border-top-color:#f59e0b;">
                              <div style="font-size:13px; color:#f59e0b; font-weight:700; text-transform:uppercase;">3. Cryptographic Proof</div>
                              <div style="font-size:22px; font-weight:700; margin:10px 0;">SHA-256 Hash Chain Audit</div>
                              <div style="font-size:15px; color:#94a3b8; line-height:1.5;">Every AI thought, store comparison, policy verdict, and PayPal capture ID is linked in a tamper-evident ledger.</div>
                            </div>
                          </div>
                        `;
                    }"""
                )
            elif elapsed >= 1.2 and elapsed < 3.5:
                await pg.evaluate("() => { const el = document.getElementById('s1-b1'); if(el){el.style.opacity='1'; el.style.transform='translateY(0)';} }")
            elif elapsed >= 3.5 and elapsed < 6.5:
                await pg.evaluate("() => { const el = document.getElementById('s1-b2'); if(el){el.style.opacity='1'; el.style.transform='translateY(0)';} }")
            elif elapsed >= 6.5:
                await pg.evaluate("() => { const el = document.getElementById('s1-b3'); if(el){el.style.opacity='1'; el.style.transform='translateY(0)';} }")

        print("  Recording Scene 1 (Intro)...")
        scene_videos.append(await record_frames_for_scene(page, SCENES[0], s1_timeline))

        # --- SCENE 2: Animated 8-Step Pipeline + Transition to Live UI ---
        async def s2_timeline(pg, f_idx, elapsed, progress):
            if f_idx == 0:
                await pg.evaluate(
                    """() => {
                        const m = document.getElementById('demo-slide-modal');
                        m.style.display = 'flex';
                        m.style.opacity = '1';
                        m.innerHTML = `
                          <div style="font-size:14px; font-weight:700; color:#38bdf8; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:10px;">End-to-End Architecture</div>
                          <div style="font-size:40px; font-weight:800;">Guardrailed 8-Step Agentic Purchase Pipeline</div>
                          <div class="pipeline-row">
                            <div class="pipe-step" id="ps-1">
                              <div style="font-size:12px; color:#38bdf8; font-weight:700;">STEP 1</div>
                              <div style="font-size:18px; font-weight:700; margin:6px 0;">AI Goal &amp; Intent</div>
                              <div style="font-size:13px; color:#94a3b8;">Recipe decomposition &amp; Pantry stock check</div>
                            </div>
                            <div class="pipe-step" id="ps-2">
                              <div style="font-size:12px; color:#38bdf8; font-weight:700;">STEP 2</div>
                              <div style="font-size:18px; font-weight:700; margin:6px 0;">5-Store Aggregator</div>
                              <div style="font-size:13px; color:#94a3b8;">Quick10, ZipBasket, CornerStore, MegaMart, BulkBarn</div>
                            </div>
                            <div class="pipe-step" id="ps-3">
                              <div style="font-size:12px; color:#38bdf8; font-weight:700;">STEP 3</div>
                              <div style="font-size:18px; font-weight:700; margin:6px 0;">SLA Utility Router</div>
                              <div style="font-size:13px; color:#94a3b8;">Dynamic urgency weights (Price vs ETA vs Rating)</div>
                            </div>
                            <div class="pipe-step" id="ps-4">
                              <div style="font-size:12px; color:#10b981; font-weight:700;">STEP 4</div>
                              <div style="font-size:18px; font-weight:700; margin:6px 0;">9-Rule Mandate</div>
                              <div style="font-size:13px; color:#94a3b8;">ALLOW, NEEDS_APPROVAL, or DENY</div>
                            </div>
                            <div class="pipe-step" id="ps-5">
                              <div style="font-size:12px; color:#f59e0b; font-weight:700;">STEP 5</div>
                              <div style="font-size:18px; font-weight:700; margin:6px 0;">PayPal Settlement</div>
                              <div style="font-size:13px; color:#94a3b8;">OAuth2 -> v2 Order Auth -> Escrow -> Capture</div>
                            </div>
                          </div>
                        `;
                    }"""
                )
            step_num = min(5, int(progress * 6) + 1)
            if progress < 0.82:
                await pg.evaluate(
                    """(sn) => {
                        for (let i=1; i<=5; i++) {
                          const el = document.getElementById('ps-' + i);
                          if (el) el.classList.toggle('active', i <= sn);
                        }
                    }""",
                    step_num,
                )
            else:
                # Fade out slide to reveal live 3-column UI!
                await pg.evaluate(
                    """() => {
                        const m = document.getElementById('demo-slide-modal');
                        if (m) m.style.display = 'none';
                    }"""
                )

        print("  Recording Scene 2 (Architecture & Pipeline)...")
        scene_videos.append(await record_frames_for_scene(page, SCENES[1], s2_timeline))

        # --- SCENE 3: Live AI Recipe Decomposition ("I need to make paneer butter masala, order all ingredients") ---
        prompt_str = "I need to make paneer butter masala, order all ingredients"
        s3_triggered = {"sent": False}

        async def s3_timeline(pg, f_idx, elapsed, progress):
            if f_idx == 0:
                await pg.evaluate(
                    """() => {
                        const m = document.getElementById('demo-slide-modal');
                        if (m) m.style.display = 'none';
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '860px'; c.style.top = '660px'; }
                    }"""
                )
            if elapsed < 3.2:
                # Type prompt progressively into #chat-input
                chars = max(1, int((elapsed / 3.0) * len(prompt_str)))
                partial = prompt_str[:chars]
                await pg.evaluate(
                    """(txt) => {
                        const inp = document.getElementById('chat-input');
                        if (inp) inp.value = txt;
                    }""",
                    partial,
                )
            elif not s3_triggered["sent"]:
                s3_triggered["sent"] = True
                await pg.evaluate(
                    """() => {
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '1395px'; c.style.top = '660px'; c.classList.add('clicking'); }
                        const inp = document.getElementById('chat-input');
                        if (inp) inp.value = '';
                        sendChat('I need to make paneer butter masala, order all ingredients');
                        setTimeout(() => { if(c) c.classList.remove('clicking'); }, 300);
                    }"""
                )
            elif elapsed > 9.0:
                # Scroll chat & pantry smoothly so viewer sees all 5 ingredients & reasoning
                await pg.evaluate(
                    """() => {
                        const cs = document.getElementById('chat-stream');
                        if (cs) cs.scrollTop = cs.scrollHeight;
                    }"""
                )

        print("  Recording Scene 3 (Paneer Butter Masala AI Reasoning & 5 PayPal Orders)...")
        scene_videos.append(await record_frames_for_scene(page, SCENES[2], s3_timeline))

        # --- SCENE 4: Pantry "Ran Out (Auto-Buy)" + "Why this store?" Score Breakdown Modal ---
        s4_state = {"depleted": False, "modal_opened": False}

        async def s4_timeline(pg, f_idx, elapsed, progress):
            if f_idx == 0:
                await pg.evaluate(
                    """() => {
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '260px'; c.style.top = '420px'; }
                    }"""
                )
            if elapsed >= 1.5 and not s4_state["depleted"]:
                s4_state["depleted"] = True
                await pg.evaluate(
                    """() => {
                        const c = document.getElementById('demo-cursor');
                        if (c) c.classList.add('clicking');
                        changeStock('item-paper', 'A4 Copy Paper 500ct', 'finished', 0);
                        setTimeout(() => { if(c) c.classList.remove('clicking'); }, 300);
                    }"""
                )
            elif elapsed >= 6.0 and not s4_state["modal_opened"]:
                s4_state["modal_opened"] = True
                await pg.evaluate(
                    """() => {
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '1780px'; c.style.top = '260px'; c.classList.add('clicking'); }
                        if (state.orders && state.orders.length > 0) {
                          showWhyStore(state.orders[0].id);
                        }
                        setTimeout(() => { if(c) c.classList.remove('clicking'); }, 300);
                    }"""
                )
            elif progress > 0.90:
                await pg.evaluate("() => closeModal('store-modal')")

        print("  Recording Scene 4 (Pantry Depletion & Why This Store Modal)...")
        scene_videos.append(await record_frames_for_scene(page, SCENES[3], s4_timeline))

        # --- SCENE 5: Untracked Item Approval Gate (WD-40) -> 1-Click Approve ---
        s5_state = {"requested": False, "approved": False}

        async def s5_timeline(pg, f_idx, elapsed, progress):
            if f_idx == 0:
                await pg.evaluate(
                    """() => {
                        closeModal('store-modal');
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '980px'; c.style.top = '610px'; }
                    }"""
                )
            if elapsed >= 1.2 and not s5_state["requested"]:
                s5_state["requested"] = True
                await pg.evaluate(
                    """() => {
                        const c = document.getElementById('demo-cursor');
                        if (c) c.classList.add('clicking');
                        sendChat('Order WD-40');
                        setTimeout(() => { if(c) c.classList.remove('clicking'); }, 300);
                    }"""
                )
            elif elapsed >= 6.8 and not s5_state["approved"]:
                s5_state["approved"] = True
                await pg.evaluate(
                    """() => {
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '620px'; c.style.top = '250px'; c.classList.add('clicking'); }
                        if (state.approvals && state.approvals.length > 0) {
                          decideApproval(state.approvals[0].intent_id, 'approve');
                        }
                        setTimeout(() => { if(c) c.classList.remove('clicking'); }, 300);
                    }"""
                )

        print("  Recording Scene 5 (WD-40 Mandate Approval Gate)...")
        scene_videos.append(await record_frames_for_scene(page, SCENES[4], s5_timeline))

        # --- SCENE 6: SHA-256 Audit Log, Kill Switch & Finale Slide ---
        s6_state = {"audit": False, "kill": False, "outro": False}

        async def s6_timeline(pg, f_idx, elapsed, progress):
            if elapsed >= 0.8 and not s6_state["audit"]:
                s6_state["audit"] = True
                await pg.evaluate(
                    """() => {
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '1820px'; c.style.top = '740px'; c.classList.add('clicking'); }
                        openAuditModal();
                        setTimeout(() => { if(c) c.classList.remove('clicking'); }, 300);
                    }"""
                )
            elif elapsed >= 5.5 and not s6_state["kill"]:
                s6_state["kill"] = True
                await pg.evaluate(
                    """() => {
                        closeModal('audit-modal');
                        const c = document.getElementById('demo-cursor');
                        if (c) { c.style.left = '1710px'; c.style.top = '38px'; c.classList.add('clicking'); }
                        toggleKillSwitch(true);
                        setTimeout(() => { if(c) c.classList.remove('clicking'); }, 300);
                    }"""
                )
            elif progress >= 0.62 and not s6_state["outro"]:
                s6_state["outro"] = True
                await pg.evaluate(
                    """() => {
                        toggleKillSwitch(false);
                        const m = document.getElementById('demo-slide-modal');
                        m.style.display = 'flex';
                        m.style.opacity = '1';
                        m.innerHTML = `
                          <div style="width:82px; height:82px; border-radius:20px; background:#0070ba; display:flex; align-items:center; justify-content:center; font-size:36px; font-weight:800; margin-bottom:22px; box-shadow:0 0 45px rgba(0,112,186,0.8);">CP</div>
                          <div style="font-size:52px; font-weight:800; margin-bottom:12px;">CommPal</div>
                          <div style="font-size:24px; color:#38bdf8; font-weight:600; margin-bottom:28px;">Autonomous Agentic Commerce &amp; Multi-Store Aggregation</div>
                          <div style="display:flex; gap:18px; flex-wrap:wrap; justify-content:center;">
                            <span style="padding:10px 20px; border-radius:99px; background:#131722; border:1px solid #2b3548; font-size:16px;">✓ PayPal REST API v2 Sandbox</span>
                            <span style="padding:10px 20px; border-radius:99px; background:#131722; border:1px solid #2b3548; font-size:16px;">✓ 9-Rule Spending Mandate</span>
                            <span style="padding:10px 20px; border-radius:99px; background:#131722; border:1px solid #2b3548; font-size:16px;">✓ AI Recipe &amp; Goal Decomposition</span>
                            <span style="padding:10px 20px; border-radius:99px; background:#131722; border:1px solid #2b3548; font-size:16px;">✓ SHA-256 Tamper-Evident Audit Chain</span>
                          </div>
                        `;
                    }"""
                )

        print("  Recording Scene 6 (Audit Chain, Kill Switch & Finale)...")
        scene_videos.append(await record_frames_for_scene(page, SCENES[5], s6_timeline))

        await browser.close()

    # Reset demo back to clean state after recording
    httpx.post("http://127.0.0.1:8000/api/demo/reset", timeout=10.0)

    # 3. Concatenate all 6 scene MP4s into commpal_demo.mp4
    print("3/4 Mastering final 1080p MP4 video (commpal_demo.mp4)...")
    concat_list = BUILD_DIR / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sv in scene_videos:
            f.write(f"file '{sv.as_posix()}'\n")

    subprocess.run(
        [
            FFMPEG_EXE,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(OUTPUT_MP4),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    # Clean up temporary build directory
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    size_mb = OUTPUT_MP4.stat().st_size / (1024 * 1024)
    print(f"4/4 Done! Saved {OUTPUT_MP4} ({size_mb:.2f} MB, {total_dur:.1f}s)")


if __name__ == "__main__":
    asyncio.run(build_video())

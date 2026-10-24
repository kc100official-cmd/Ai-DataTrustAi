import React, { useEffect, useRef, useState } from 'react';

interface InteractiveAtmosphereProps {
  cursorEnabled: boolean;
}

interface ShootingStar {
  x: number;
  y: number;
  vx: number;
  vy: number;
  len: number;
  alpha: number;
  maxAlpha: number;
  life: number;
  maxLife: number;
  hue: number;
  thickness: number;
}

export const InteractiveAtmosphere: React.FC<InteractiveAtmosphereProps> = ({ cursorEnabled }) => {
  const curDotRef = useRef<HTMLDivElement>(null);
  const curRingRef = useRef<HTMLDivElement>(null);
  const curGlowRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isHoveringInteractive, setIsHoveringInteractive] = useState(false);
  const [isClicking, setIsClicking] = useState(false);

  // Toggle class on <html> and <body> for strict native-cursor hiding
  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    if (cursorEnabled) {
      html.classList.add('custom-cursor-enabled');
      body.classList.add('custom-cursor-enabled');
    } else {
      html.classList.remove('custom-cursor-enabled');
      body.classList.remove('custom-cursor-enabled');
    }
    return () => {
      html.classList.remove('custom-cursor-enabled');
      body.classList.remove('custom-cursor-enabled');
    };
  }, [cursorEnabled]);

  // 60 FPS Zero-Reflow GPU-Accelerated Custom Cursor
  useEffect(() => {
    if (!cursorEnabled) return;

    let cmx = window.innerWidth / 2;
    let cmy = window.innerHeight / 2;
    let crx = cmx;
    let cry = cmy;
    let lastHoverState = false;
    let lastTime = performance.now();
    let rafId: number | null = null;

    const onMouseMove = (e: MouseEvent) => {
      cmx = e.clientX;
      cmy = e.clientY;

      // Instant 0ms GPU transform for inner dot
      if (curDotRef.current) {
        curDotRef.current.style.transform = `translate3d(${cmx}px, ${cmy}px, 0) translate(-50%, -50%)`;
      }

      // Lightweight tag check without triggering synchronous layout reflow (no getBoundingClientRect)
      const target = e.target as HTMLElement | null;
      if (target) {
        const interactiveEl = target.closest(
          'a, button, input, select, textarea, label, canvas, [role="button"], .btn-nexus, .btn-nexus-outline, .cursor-pointer'
        );
        const nextHover = Boolean(interactiveEl);
        if (nextHover !== lastHoverState) {
          lastHoverState = nextHover;
          setIsHoveringInteractive(nextHover);
        }
      }
    };

    const onMouseDown = () => setIsClicking(true);
    const onMouseUp = () => setIsClicking(false);

    const loop = (now: number) => {
      rafId = requestAnimationFrame(loop);
      if (document.hidden) return;

      const dt = Math.min((now - lastTime) / 16.667, 2.5);
      lastTime = now;

      // Frame-rate independent 60fps spring follow for outer halo ring
      const alpha = 1 - Math.pow(1 - 0.58, dt);
      crx += (cmx - crx) * alpha;
      cry += (cmy - cry) * alpha;

      const transformStr = `translate3d(${crx.toFixed(1)}px, ${cry.toFixed(1)}px, 0) translate(-50%, -50%)`;
      if (curRingRef.current) {
        curRingRef.current.style.transform = transformStr;
      }
      if (curGlowRef.current) {
        curGlowRef.current.style.transform = transformStr;
      }
    };

    window.addEventListener('mousemove', onMouseMove, { passive: true });
    window.addEventListener('mousedown', onMouseDown, { passive: true });
    window.addEventListener('mouseup', onMouseUp, { passive: true });
    rafId = requestAnimationFrame(loop);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mouseup', onMouseUp);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [cursorEnabled]);

  // 60 FPS Hardware-Accelerated Pre-Cached Sprite Background Canvas
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext('2d', { alpha: false });
    if (!ctx) return;

    let pmW = (cv.width = window.innerWidth);
    let pmH = (cv.height = window.innerHeight);
    let pmScrollY = window.scrollY;
    let pmTargetY = window.scrollY;
    let mouseX = pmW * 0.5;
    let mouseY = pmH * 0.5;
    let smoothMouseX = mouseX;
    let smoothMouseY = mouseY;
    let time = 0;
    let lastFrameTime = performance.now();
    let rafId: number | null = null;

    const onResize = () => {
      if (!cv) return;
      pmW = cv.width = window.innerWidth;
      pmH = cv.height = window.innerHeight;
    };

    const onScroll = () => {
      pmTargetY = window.scrollY;
    };

    const onMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    };

    // Pre-render aurora nebula blobs once to offscreen canvases (zero per-frame gradient allocations!)
    const blobConfigs = [
      { xFactor: 0.20, yFactor: 0.24, r: 520, speedX: 0.0005, speedY: 0.0007, phase: 0.0, color: '99, 102, 241', alpha: 0.26 },
      { xFactor: 0.78, yFactor: 0.30, r: 540, speedX: 0.0006, speedY: 0.0004, phase: 2.1, color: '56, 189, 248', alpha: 0.20 },
      { xFactor: 0.50, yFactor: 0.72, r: 500, speedX: 0.0004, speedY: 0.0006, phase: 4.2, color: '168, 85, 247', alpha: 0.22 },
      { xFactor: 0.16, yFactor: 0.80, r: 420, speedX: 0.0008, speedY: 0.0005, phase: 1.4, color: '245, 158, 11', alpha: 0.14 },
      { xFactor: 0.84, yFactor: 0.78, r: 410, speedX: 0.0005, speedY: 0.0006, phase: 3.1, color: '244, 114, 182', alpha: 0.14 },
    ];

    const preRenderedBlobs = blobConfigs.map((b) => {
      const spriteSize = 256;
      const off = document.createElement('canvas');
      off.width = spriteSize;
      off.height = spriteSize;
      const octx = off.getContext('2d');
      if (octx) {
        const half = spriteSize / 2;
        const grad = octx.createRadialGradient(half, half, 0, half, half, half);
        grad.addColorStop(0, `rgba(${b.color}, ${b.alpha})`);
        grad.addColorStop(0.55, `rgba(${b.color}, ${b.alpha * 0.45})`);
        grad.addColorStop(1, 'rgba(16, 22, 47, 0)');
        octx.fillStyle = grad;
        octx.fillRect(0, 0, spriteSize, spriteSize);
      }
      return { ...b, sprite: off };
    });

    // Fast single-pass starfield (no per-frame createRadialGradient!)
    const stars = Array.from({ length: 110 }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight * 2.5,
      r: 0.8 + Math.random() * 1.4,
      speed: 0.08 + Math.random() * 0.28,
      a: 0.35 + Math.random() * 0.6,
      twinkleSpeed: 0.02 + Math.random() * 0.03,
      twinklePhase: Math.random() * Math.PI * 2,
      color: Math.random() > 0.3 ? '#e0e7ff' : '#fde68a',
    }));

    const shootingStars: ShootingStar[] = [];

    const spawnShootingStar = () => {
      const startX = Math.random() * pmW * 1.05;
      const startY = Math.random() * pmH * 0.5;
      const angle = (Math.PI / 180) * (22 + Math.random() * 24);
      const speed = 12 + Math.random() * 8;
      const hues = [45, 210, 265, 325];
      shootingStars.push({
        x: startX,
        y: startY,
        vx: Math.cos(angle) * speed * (Math.random() > 0.15 ? 1 : -1),
        vy: Math.sin(angle) * speed,
        len: 120 + Math.random() * 130,
        alpha: 0,
        maxAlpha: 0.85,
        life: 0,
        maxLife: 42 + Math.random() * 28,
        hue: hues[Math.floor(Math.random() * hues.length)],
        thickness: 1.6 + Math.random() * 1.0,
      });
    };

    for (let i = 0; i < 2; i++) {
      spawnShootingStar();
    }

    const draw = (now: number) => {
      rafId = requestAnimationFrame(draw);
      if (document.hidden) return;

      // Locked 60 FPS delta-time multiplier (1.0 at 60Hz)
      const dt = Math.min((now - lastFrameTime) / 16.667, 2.2);
      lastFrameTime = now;

      time += dt;
      pmScrollY += (pmTargetY - pmScrollY) * (1 - Math.pow(1 - 0.06, dt));
      smoothMouseX += (mouseX - smoothMouseX) * (1 - Math.pow(1 - 0.05, dt));
      smoothMouseY += (mouseY - smoothMouseY) * (1 - Math.pow(1 - 0.05, dt));

      // 1. Base fill (#10162f)
      ctx.fillStyle = '#10162f';
      ctx.fillRect(0, 0, pmW, pmH);

      // 2. Fast GPU-blitted pre-rendered aurora blobs
      for (let i = 0; i < preRenderedBlobs.length; i++) {
        const b = preRenderedBlobs[i];
        const bx =
          pmW * b.xFactor +
          Math.sin(time * b.speedX * 60 + b.phase) * 135 +
          (smoothMouseX - pmW * 0.5) * 0.07;
        const by =
          pmH * b.yFactor +
          Math.cos(time * b.speedY * 60 + b.phase) * 105 +
          (smoothMouseY - pmH * 0.5) * 0.07;
        ctx.drawImage(b.sprite, bx - b.r, by - b.r, b.r * 2, b.r * 2);
      }

      // 3. Silk wave ribbons
      for (let w = 0; w < 3; w++) {
        ctx.beginPath();
        const baseY = pmH * (0.28 + w * 0.26);
        for (let x = 0; x <= pmW; x += 36) {
          const waveY =
            baseY +
            Math.sin(x * 0.0032 + time * 0.016 + w * 1.7) * 44 +
            Math.cos(x * 0.007 - time * 0.011 + w) * 22 +
            (smoothMouseY - pmH * 0.5) * 0.035;
          if (x === 0) ctx.moveTo(x, waveY);
          else ctx.lineTo(x, waveY);
        }
        ctx.strokeStyle =
          w === 0
            ? 'rgba(167, 139, 250, 0.09)'
            : w === 1
            ? 'rgba(251, 191, 36, 0.065)'
            : 'rgba(56, 189, 248, 0.08)';
        ctx.lineWidth = 2.0;
        ctx.stroke();
      }

      // 4. Ultra-fast single-pass starfield
      const parallaxX = (smoothMouseX / pmW - 0.5) * 36;
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        const sx = ((s.x + parallaxX * s.speed) % pmW + pmW) % pmW;
        const sy = ((s.y - pmScrollY * s.speed) % pmH + pmH) % pmH;
        const twinkle = 0.65 + 0.35 * Math.sin(time * s.twinkleSpeed + s.twinklePhase);
        ctx.globalAlpha = s.a * twinkle;
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1.0;

      // 5. 60 FPS Shooting Stars
      if (Math.random() < 0.028 * dt && shootingStars.length < 4) {
        spawnShootingStar();
      }

      for (let i = shootingStars.length - 1; i >= 0; i--) {
        const st = shootingStars[i];
        st.x += st.vx * dt;
        st.y += st.vy * dt;
        st.life += dt;

        const progress = st.life / st.maxLife;
        if (progress < 0.2) {
          st.alpha = (progress / 0.2) * st.maxAlpha;
        } else {
          st.alpha = Math.max(0, (1 - (progress - 0.2) / 0.8) * st.maxAlpha);
        }

        const speedMag = Math.hypot(st.vx, st.vy) || 1;
        const tailX = st.x - (st.vx / speedMag) * st.len;
        const tailY = st.y - (st.vy / speedMag) * st.len;

        const tailGrad = ctx.createLinearGradient(st.x, st.y, tailX, tailY);
        tailGrad.addColorStop(0, `hsla(${st.hue}, 100%, 95%, ${st.alpha})`);
        tailGrad.addColorStop(0.3, `hsla(${st.hue}, 95%, 72%, ${st.alpha * 0.6})`);
        tailGrad.addColorStop(1, 'transparent');

        ctx.beginPath();
        ctx.moveTo(st.x, st.y);
        ctx.lineTo(tailX, tailY);
        ctx.strokeStyle = tailGrad;
        ctx.lineWidth = st.thickness;
        ctx.lineCap = 'round';
        ctx.stroke();

        ctx.fillStyle = `rgba(255, 255, 255, ${st.alpha})`;
        ctx.beginPath();
        ctx.arc(st.x, st.y, 2.4, 0, Math.PI * 2);
        ctx.fill();

        if (st.life >= st.maxLife || st.x < -200 || st.x > pmW + 200 || st.y > pmH + 200) {
          shootingStars.splice(i, 1);
        }
      }
    };

    window.addEventListener('resize', onResize, { passive: true });
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('mousemove', onMouseMove, { passive: true });
    rafId = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('mousemove', onMouseMove);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        className="fixed inset-0 pointer-events-none z-0"
        style={{ willChange: 'transform', transform: 'translateZ(0)' }}
        aria-hidden="true"
      />

      {cursorEnabled && (
        <div className="pointer-events-none fixed inset-0 z-[99999]">
          <div
            ref={curGlowRef}
            style={{
              position: 'fixed',
              left: 0,
              top: 0,
              width: '120px',
              height: '120px',
              background: 'radial-gradient(circle, rgba(167, 139, 250, 0.14) 0%, transparent 70%)',
              borderRadius: '50%',
              transform: 'translate3d(-200px, -200px, 0)',
              willChange: 'transform',
            }}
          />
          <div
            ref={curDotRef}
            style={{
              position: 'fixed',
              left: 0,
              top: 0,
              width: isClicking ? '6px' : '9px',
              height: isClicking ? '6px' : '9px',
              background: isHoveringInteractive ? '#fde68a' : '#ffffff',
              borderRadius: '50%',
              transform: 'translate3d(-200px, -200px, 0)',
              boxShadow: isHoveringInteractive
                ? '0 0 16px rgba(251, 191, 36, 0.95)'
                : '0 0 12px rgba(255, 255, 255, 0.9)',
              willChange: 'transform',
            }}
          />
          <div
            ref={curRingRef}
            style={{
              position: 'fixed',
              left: 0,
              top: 0,
              width: isClicking ? '24px' : isHoveringInteractive ? '44px' : '32px',
              height: isClicking ? '24px' : isHoveringInteractive ? '44px' : '32px',
              border: isHoveringInteractive
                ? '1.5px solid rgba(253, 230, 138, 0.95)'
                : '1.5px solid rgba(255, 255, 255, 0.55)',
              background: isHoveringInteractive
                ? 'radial-gradient(circle, rgba(251, 191, 36, 0.14) 0%, transparent 75%)'
                : 'transparent',
              borderRadius: '50%',
              transform: 'translate3d(-200px, -200px, 0)',
              transition:
                'width 0.12s cubic-bezier(0.16, 1, 0.3, 1), height 0.12s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.12s ease',
              willChange: 'transform',
            }}
          />
        </div>
      )}
    </>
  );
};

export const NexusIntroLoader: React.FC<{ onFinish: () => void }> = ({ onFinish }) => {
  const [progress, setProgress] = useState(0);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    const iv = setInterval(() => {
      setProgress((prev) => {
        const next = prev + 25 + Math.floor(Math.random() * 25);
        if (next >= 100) {
          clearInterval(iv);
          setTimeout(() => setFading(true), 80);
          setTimeout(() => onFinish(), 380);
          return 100;
        }
        return next;
      });
    }, 75);
    return () => clearInterval(iv);
  }, [onFinish]);

  return (
    <div
      onClick={onFinish}
      className={`fixed inset-0 z-[10000] flex items-center justify-center transition-opacity duration-300 ${
        fading ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
      style={{
        background: 'radial-gradient(circle at 50% 42%, rgba(99, 102, 241, 0.35), transparent 62%), #10162f',
      }}
    >
      <div className="text-center select-none">
        <div className="relative w-[88px] h-[88px] mx-auto mb-6 flex items-center justify-center">
          <div className="nexus-ldr-ring" />
          <div className="nexus-ldr-ring2" />
          <div
            className="relative z-10 w-[54px] h-[54px] rounded-2xl border border-white/40 flex items-center justify-center font-display font-bold text-lg text-white"
            style={{
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.7), rgba(168, 85, 247, 0.7))',
              backdropFilter: 'blur(12px)',
              boxShadow: '0 0 32px rgba(129, 140, 248, 0.55)',
            }}
          >
            DT
          </div>
        </div>
        <div className="font-display font-bold text-base tracking-[0.08em] text-white mb-2">
          DataTrust AI
        </div>
        <div className="w-44 h-[3px] bg-white/15 mx-auto mb-2 overflow-hidden rounded-full">
          <div
            className="h-full transition-all duration-150"
            style={{
              width: `${progress}%`,
              background: 'linear-gradient(90deg, #818cf8, #fbbf24)',
            }}
          />
        </div>
      </div>
    </div>
  );
};

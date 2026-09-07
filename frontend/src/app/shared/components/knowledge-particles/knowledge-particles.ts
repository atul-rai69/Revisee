import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
}

export const MAX_KNOWLEDGE_PARTICLES = 52;
export const TABLET_PARTICLE_CAP = 28;

export function particleCountForArea(area: number, compact: boolean): number {
  const areaCount = Math.max(10, Math.floor(Math.max(0, area) / 18000));
  return Math.min(compact ? TABLET_PARTICLE_CAP : MAX_KNOWLEDGE_PARTICLES, areaCount);
}

function mediaQuery(query: string): MediaQueryList {
  if (typeof window.matchMedia === 'function') return window.matchMedia(query);
  return {
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  };
}

@Component({
  selector: 'app-knowledge-particles',
  templateUrl: './knowledge-particles.html',
  styleUrl: './knowledge-particles.css',
})
export class KnowledgeParticles implements AfterViewInit, OnDestroy {
  @ViewChild('canvas', { static: true }) private canvasRef!: ElementRef<HTMLCanvasElement>;

  private context: CanvasRenderingContext2D | null = null;
  private host: HTMLElement | null = null;
  private pointerSurface: HTMLElement | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private animationFrame: number | null = null;
  private lastFrameTime = 0;
  private width = 0;
  private height = 0;
  private particles: Particle[] = [];
  private pointerX = 0;
  private pointerY = 0;
  private pointerActive = false;
  private readonly reducedMotion = mediaQuery('(prefers-reduced-motion: reduce)');
  private readonly compactViewport = mediaQuery('(max-width: 900px)');
  private readonly mobileViewport = mediaQuery('(max-width: 720px)');

  ngAfterViewInit(): void {
    try {
      this.context = this.canvasRef.nativeElement.getContext('2d');
    } catch {
      this.context = null;
    }
    if (!this.context) return;

    this.host = this.canvasRef.nativeElement.parentElement;
    if (!this.host) return;
    this.pointerSurface = this.host.parentElement ?? this.host;

    this.pointerSurface.addEventListener('pointermove', this.handlePointerMove);
    this.pointerSurface.addEventListener('pointerleave', this.handlePointerLeave);
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
    this.reducedMotion.addEventListener('change', this.handleMotionChange);
    this.compactViewport.addEventListener('change', this.handleMotionChange);
    this.mobileViewport.addEventListener('change', this.handleMotionChange);

    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.host);
    } else {
      window.addEventListener('resize', this.resize);
    }
    this.resize();
  }

  ngOnDestroy(): void {
    this.stopAnimation();
    this.resizeObserver?.disconnect();
    window.removeEventListener('resize', this.resize);
    document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    this.reducedMotion.removeEventListener('change', this.handleMotionChange);
    this.compactViewport.removeEventListener('change', this.handleMotionChange);
    this.mobileViewport.removeEventListener('change', this.handleMotionChange);
    this.pointerSurface?.removeEventListener('pointermove', this.handlePointerMove);
    this.pointerSurface?.removeEventListener('pointerleave', this.handlePointerLeave);
  }

  private readonly resize = (): void => {
    if (!this.context || !this.host) return;
    const bounds = this.host.getBoundingClientRect();
    this.width = Math.max(0, bounds.width);
    this.height = Math.max(0, bounds.height);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const canvas = this.canvasRef.nativeElement;
    canvas.width = Math.max(1, Math.round(this.width * ratio));
    canvas.height = Math.max(1, Math.round(this.height * ratio));
    canvas.style.width = `${this.width}px`;
    canvas.style.height = `${this.height}px`;
    this.context.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.resetParticles();
    this.restartForPreferences();
  };

  private resetParticles(): void {
    const count = particleCountForArea(
      this.width * this.height,
      this.compactViewport.matches,
    );
    this.particles = Array.from({ length: count }, () => ({
      x: Math.random() * this.width,
      y: Math.random() * this.height,
      vx: (Math.random() - 0.5) * 5,
      vy: (Math.random() - 0.5) * 5,
      radius: 0.8 + Math.random() * 1.7,
      alpha: 0.25 + Math.random() * 0.5,
    }));
  }

  private restartForPreferences(): void {
    this.stopAnimation();
    this.draw(0, false);
    if (!this.reducedMotion.matches && !this.mobileViewport.matches && !document.hidden && this.width > 0) {
      this.startAnimation();
    }
  }

  private startAnimation(): void {
    if (this.animationFrame !== null) return;
    this.lastFrameTime = performance.now();
    this.animationFrame = requestAnimationFrame(this.animate);
  }

  private stopAnimation(): void {
    if (this.animationFrame !== null) cancelAnimationFrame(this.animationFrame);
    this.animationFrame = null;
  }

  private readonly animate = (timestamp: number): void => {
    const deltaSeconds = Math.min(Math.max((timestamp - this.lastFrameTime) / 1000, 0), 0.05);
    this.lastFrameTime = timestamp;
    this.draw(deltaSeconds, true);
    this.animationFrame = requestAnimationFrame(this.animate);
  };

  private draw(deltaSeconds: number, advance: boolean): void {
    const context = this.context;
    if (!context) return;
    context.clearRect(0, 0, this.width, this.height);
    const centerX = this.width * 0.52;
    const centerY = this.height * 0.58;

    context.save();
    context.strokeStyle = 'rgba(130, 244, 225, 0.28)';
    context.lineWidth = 1;
    for (let orbit = 0; orbit < 3; orbit += 1) {
      context.beginPath();
      context.ellipse(centerX, centerY, this.width * (0.28 + orbit * 0.09), this.height * (0.13 + orbit * 0.045), -0.28 + orbit * 0.22, 0, Math.PI * 2);
      context.stroke();
    }
    context.restore();

    for (let index = 0; index < this.particles.length; index += 1) {
      const particle = this.particles[index];
      if (advance) this.advanceParticle(particle, deltaSeconds);
      for (let otherIndex = index + 1; otherIndex < this.particles.length; otherIndex += 1) {
        const other = this.particles[otherIndex];
        const dx = other.x - particle.x;
        const dy = other.y - particle.y;
        const distanceSquared = dx * dx + dy * dy;
        if (distanceSquared < 6200) {
          context.beginPath();
          context.strokeStyle = `rgba(139, 245, 223, ${0.11 * (1 - distanceSquared / 6200)})`;
          context.moveTo(particle.x, particle.y);
          context.lineTo(other.x, other.y);
          context.stroke();
        }
      }
      context.beginPath();
      context.fillStyle = `rgba(220, 255, 247, ${particle.alpha})`;
      context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
      context.fill();
    }
  }

  private advanceParticle(particle: Particle, deltaSeconds: number): void {
    particle.x += particle.vx * deltaSeconds;
    particle.y += particle.vy * deltaSeconds;
    if (this.pointerActive) {
      const dx = particle.x - this.pointerX;
      const dy = particle.y - this.pointerY;
      const distanceSquared = Math.max(dx * dx + dy * dy, 80);
      if (distanceSquared < 9000) {
        const force = 1500 / distanceSquared;
        particle.x += dx * force * deltaSeconds;
        particle.y += dy * force * deltaSeconds;
      }
    }
    if (particle.x < -4) particle.x = this.width + 4;
    else if (particle.x > this.width + 4) particle.x = -4;
    if (particle.y < -4) particle.y = this.height + 4;
    else if (particle.y > this.height + 4) particle.y = -4;
  }

  private readonly handlePointerMove = (event: PointerEvent): void => {
    if (!this.pointerSurface) return;
    const bounds = this.pointerSurface.getBoundingClientRect();
    this.pointerX = event.clientX - bounds.left;
    this.pointerY = event.clientY - bounds.top;
    this.pointerActive = true;
  };

  private readonly handlePointerLeave = (): void => {
    this.pointerActive = false;
  };

  private readonly handleVisibilityChange = (): void => {
    if (document.hidden) this.stopAnimation();
    else this.restartForPreferences();
  };

  private readonly handleMotionChange = (): void => this.restartForPreferences();
}

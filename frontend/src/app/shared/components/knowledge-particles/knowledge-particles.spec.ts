import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { KnowledgeParticles, MAX_KNOWLEDGE_PARTICLES, TABLET_PARTICLE_CAP, particleCountForArea } from './knowledge-particles';

describe('KnowledgeParticles', () => {
  let fixture: ComponentFixture<KnowledgeParticles>;
  let reducedMotion = false;
  let mobile = false;
  let disconnect: ReturnType<typeof vi.fn>;
  let originalHidden: PropertyDescriptor | undefined;
  let originalMatchMedia: typeof window.matchMedia | undefined;
  let requestFrame: ReturnType<typeof vi.fn>;

  const context = {
    clearRect: vi.fn(), save: vi.fn(), restore: vi.fn(), beginPath: vi.fn(), ellipse: vi.fn(),
    stroke: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), arc: vi.fn(), fill: vi.fn(), setTransform: vi.fn(),
    strokeStyle: '', fillStyle: '', lineWidth: 1,
  } as unknown as CanvasRenderingContext2D;

  beforeEach(() => {
    originalHidden = Object.getOwnPropertyDescriptor(document, 'hidden');
    originalMatchMedia = window.matchMedia;
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 800, height: 600, top: 0, left: 0, right: 800, bottom: 600, x: 0, y: 0, toJSON: () => ({}),
    });
    requestFrame = vi.fn(() => 11);
    vi.stubGlobal('requestAnimationFrame', requestFrame);
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    Object.defineProperty(window, 'matchMedia', { configurable: true, writable: true, value: vi.fn((query: string) => ({
      matches: query.includes('prefers-reduced-motion') ? reducedMotion : query.includes('720px') ? mobile : false,
      media: query, onchange: null, addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    })) });
    disconnect = vi.fn();
    vi.stubGlobal('ResizeObserver', class {
      observe = vi.fn();
      disconnect = disconnect;
    });
  });

  afterEach(() => {
    fixture?.destroy();
    if (originalHidden) Object.defineProperty(document, 'hidden', originalHidden);
    Object.defineProperty(window, 'matchMedia', { configurable: true, writable: true, value: originalMatchMedia });
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function create(): number {
    TestBed.configureTestingModule({ imports: [KnowledgeParticles] });
    fixture = TestBed.createComponent(KnowledgeParticles);
    const callsBeforeAngularLifecycle = requestFrame.mock.calls.length;
    fixture.detectChanges();
    return requestFrame.mock.calls.length - callsBeforeAngularLifecycle;
  }

  it('starts one loop and tears down its frame and observer', () => {
    const removeDocumentListener = vi.spyOn(document, 'removeEventListener');
    const removeSurfaceListener = vi.spyOn(HTMLElement.prototype, 'removeEventListener');
    expect(create()).toBe(1);
    fixture.destroy();
    expect(cancelAnimationFrame).toHaveBeenCalledWith(11);
    expect(disconnect).toHaveBeenCalled();
    expect(removeDocumentListener).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
    expect(removeSurfaceListener).toHaveBeenCalledWith('pointermove', expect.any(Function));
    expect(removeSurfaceListener).toHaveBeenCalledWith('pointerleave', expect.any(Function));
  });

  it('pauses and resumes the same field for page visibility changes', () => {
    let hidden = false;
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
    create();
    vi.mocked(cancelAnimationFrame).mockClear();
    requestFrame.mockClear();
    hidden = true;
    document.dispatchEvent(new Event('visibilitychange'));
    expect(cancelAnimationFrame).toHaveBeenCalledWith(11);
    hidden = false;
    document.dispatchEvent(new Event('visibilitychange'));
    expect(requestFrame).toHaveBeenCalledTimes(1);
  });

  it('renders a quiet static state in reduced motion', () => {
    reducedMotion = true;
    expect(create()).toBe(0);
    expect(context.clearRect).toHaveBeenCalled();
  });

  it('does not animate the particle field when its mobile panel is hidden', () => {
    mobile = true;
    expect(create()).toBe(0);
  });

  it('caps particle counts for desktop and tablet areas', () => {
    expect(particleCountForArea(10_000_000, false)).toBe(MAX_KNOWLEDGE_PARTICLES);
    expect(particleCountForArea(10_000_000, true)).toBe(TABLET_PARTICLE_CAP);
    expect(particleCountForArea(0, false)).toBe(10);
  });

  it('marks the canvas decorative and noninteractive', () => {
    create();
    const canvas = fixture.nativeElement.querySelector('canvas') as HTMLCanvasElement;
    expect(canvas.getAttribute('aria-hidden')).toBe('true');
    expect(getComputedStyle(canvas).pointerEvents).toBe('none');
  });
});

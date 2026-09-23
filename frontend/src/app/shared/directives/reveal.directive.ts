import { isPlatformBrowser } from '@angular/common';
import { AfterViewInit, Directive, ElementRef, HostBinding, Input, OnDestroy, PLATFORM_ID, inject } from '@angular/core';

@Directive({
  selector: '[appReveal]',
})
export class RevealDirective implements AfterViewInit, OnDestroy {
  @Input() revealIndex = 0;
  @HostBinding('class.reveal-ready') readonly revealReady = true;
  @HostBinding('style.--reveal-index') get revealOrder(): string { return `${this.revealIndex}`; }

  private readonly element = inject(ElementRef<HTMLElement>);
  private readonly platformId = inject(PLATFORM_ID);
  private observer?: IntersectionObserver;

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId) || !('IntersectionObserver' in window)) {
      this.element.nativeElement.classList.add('is-revealed');
      return;
    }

    this.observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      this.element.nativeElement.classList.add('is-revealed');
      this.observer?.disconnect();
    }, { rootMargin: '0px 0px -8% 0px', threshold: .12 });
    this.observer.observe(this.element.nativeElement);
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
  }
}

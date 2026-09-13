import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RevealDirective } from './reveal.directive';

@Component({
  imports: [RevealDirective],
  template: '<section appReveal>Study content</section>',
})
class RevealHost {}

describe('RevealDirective', () => {
  let fixture: ComponentFixture<RevealHost>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [RevealHost] }).compileComponents();
    fixture = TestBed.createComponent(RevealHost);
    fixture.detectChanges();
  });

  it('shows content when IntersectionObserver is unavailable', () => {
    const section = fixture.nativeElement.querySelector('section') as HTMLElement;
    expect(section.classList).toContain('reveal-ready');
    expect(section.classList).toContain('is-revealed');
  });
});

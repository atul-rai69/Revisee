import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { Sidebar } from './sidebar';

describe('Sidebar', () => {
  let component: Sidebar;
  let fixture: ComponentFixture<Sidebar>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Sidebar],
      providers: [provideRouter([]), provideHttpClient()]
    })
    .compileComponents();

    fixture = TestBed.createComponent(Sidebar);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('keeps honest primary navigation and excludes experimental pages', () => {
    const links = [...fixture.nativeElement.querySelectorAll('.nav-item')] as HTMLAnchorElement[];
    expect(links.map((link) => link.textContent?.trim())).toEqual(['Home', 'My Learning', 'Revise', 'Topics']);
    expect(fixture.nativeElement.textContent).not.toContain('Playground');
    expect(fixture.nativeElement.textContent).not.toContain('Canvas');
    expect(fixture.nativeElement.textContent).not.toContain('Design Preview');
  });
});

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { AppLayout } from './app-layout';

describe('AppLayout', () => {
  let component: AppLayout;
  let fixture: ComponentFixture<AppLayout>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppLayout],
      providers: [provideRouter([]), provideHttpClient()]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AppLayout);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('provides a compact page bar with add-material and account actions', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.page-bar')).toBeTruthy();
    expect(element.querySelector('a[href="/app/new-item"]')).toBeTruthy();
    expect(element.querySelector('[aria-haspopup="menu"]')).toBeTruthy();
  });
});

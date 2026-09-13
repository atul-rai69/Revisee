import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SystemState } from './system-state';

describe('SystemState', () => {
  let fixture: ComponentFixture<SystemState>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [SystemState] }).compileComponents();
    fixture = TestBed.createComponent(SystemState);
    fixture.componentRef.setInput('title', 'Nothing here yet');
    fixture.componentRef.setInput('message', 'Add learning material to get started.');
    fixture.componentRef.setInput('actionLabel', 'Try again');
    fixture.detectChanges();
  });

  it('renders accessible feedback and emits its optional action', () => {
    const action = vi.fn();
    fixture.componentInstance.action.subscribe(action);
    const state = fixture.nativeElement.querySelector('section') as HTMLElement;
    expect(state.getAttribute('role')).toBe('status');
    (fixture.nativeElement.querySelector('button') as HTMLButtonElement).click();
    expect(action).toHaveBeenCalledOnce();
  });
});

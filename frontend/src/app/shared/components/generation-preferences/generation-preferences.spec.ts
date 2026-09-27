import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GenerationPreferencesPanel } from './generation-preferences';

describe('GenerationPreferencesPanel', () => {
  let fixture: ComponentFixture<GenerationPreferencesPanel>;
  let component: GenerationPreferencesPanel;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [GenerationPreferencesPanel] }).compileComponents();
    fixture = TestBed.createComponent(GenerationPreferencesPanel);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('uses backward-compatible automatic defaults until customization is enabled', () => {
    expect(component.buildPreferences()).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Generate automatically');
  });

  it('validates mixed difficulty and exposes numerical controls conditionally', () => {
    component.toggleCustomization();
    component.form.patchValue({
      typeTheory: false, typeNumerical: true, difficultyMode: 'MIXED',
      easyPercent: 10, mediumPercent: 20, hardPercent: 30,
    });
    fixture.detectChanges();
    expect(component.validationMessage()).toContain('total 100');
    expect(fixture.nativeElement.textContent).toContain('Calculation complexity');
    component.form.patchValue({ easyPercent: 20, mediumPercent: 50, hardPercent: 30 });
    expect(component.buildPreferences()?.question_types).toEqual(['NUMERICAL']);
  });

  it('labels generated PYQ content as style rather than authentic past papers', () => {
    component.toggleCustomization();
    component.form.controls.typePyqStyle.setValue(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Previous-year exam style');
    expect(fixture.nativeElement.textContent).toContain('not verified previous-year questions');
  });
});

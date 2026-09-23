import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NEVER, Subject } from 'rxjs';
import { vi } from 'vitest';

import { NewItem } from './new-item';
import { LabelService } from '../../core/services/label-service';
import { LearningItem } from '../../core/services/learning-item';
import { AICredentialsService } from '../../core/services/ai-credentials.service';
import { ToasterService } from '../../core/services/toaster.service';
import { MAX_IMAGE_UPLOAD_BYTES, MAX_PDF_UPLOAD_BYTES } from './new-item';

class FakeLabelService { getLabels() { return NEVER; } }
class FakeLearningItemService {
  readonly createResult = new Subject<{ message: string }>();
  createLearningItem = vi.fn((_body: FormData) => this.createResult.asObservable());
}
class FakeAICredentialsService {
  list() { return NEVER; }
}

describe('NewItem', () => {
  let component: NewItem;
  let fixture: ComponentFixture<NewItem>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewItem],
      providers: [
        { provide: LabelService, useClass: FakeLabelService },
        { provide: LearningItem, useClass: FakeLearningItemService },
        { provide: AICredentialsService, useClass: FakeAICredentialsService },
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(NewItem);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('sends an explicit personal credential choice and prevents duplicate submits', () => {
    const service = TestBed.inject(LearningItem) as unknown as FakeLearningItemService;
    component.learningItemForm.setValue({
      title: 'Cell biology',
      description_text: '<p>Cell notes</p>',
      generationSource: 'PERSONAL',
      credentialId: 8,
      personalRemarks: 'Use concise examples.',
    });
    component.onSubmit();
    component.onSubmit();
    expect(service.createLearningItem).toHaveBeenCalledTimes(1);
    const body = service.createLearningItem.mock.calls[0][0] as FormData;
    expect(body.get('generation_source')).toBe('PERSONAL');
    expect(body.get('credential_id')).toBe('8');
    expect(body.get('personal_remarks')).toBe('Use concise examples.');
    expect(component.saving()).toBe(true);
  });

  it('rejects oversized image and PDF selections immediately', () => {
    const toaster = TestBed.inject(ToasterService);
    const warning = vi.spyOn(toaster, 'warning');
    const image = sizedFile('large.png', 'image/png', MAX_IMAGE_UPLOAD_BYTES + 1);
    const pdf = sizedFile('large.pdf', 'application/pdf', MAX_PDF_UPLOAD_BYTES + 1);

    component.processFiles([image] as unknown as FileList);
    component.processPdfFiles([pdf] as unknown as FileList);

    expect(component.uploadedImages).toEqual([]);
    expect(component.uploadedPdfs).toEqual([]);
    expect(warning).toHaveBeenCalledTimes(2);
    expect(warning.mock.calls[0][0]).toContain('larger than 10 MB');
    expect(warning.mock.calls[1][0]).toContain('larger than 10 MB');
  });

  it('rechecks file sizes before submitting the learning item', () => {
    const service = TestBed.inject(LearningItem) as unknown as FakeLearningItemService;
    component.learningItemForm.setValue({
      title: 'Cell biology',
      description_text: '<p>Cell notes</p>',
      generationSource: 'REVISEE',
      credentialId: null,
      personalRemarks: '',
    });
    component.uploadedPdfs = [{
      file: sizedFile('large.pdf', 'application/pdf', MAX_PDF_UPLOAD_BYTES + 1),
    }];

    component.onSubmit();

    expect(service.createLearningItem).not.toHaveBeenCalled();
    expect(component.saving()).toBe(false);
  });

  it('shows the verified 10 MB per-file limits', () => {
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('WEBP up to 10MB each');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('PDF up to 10MB each');
  });
});

function sizedFile(name: string, type: string, size: number): File {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { configurable: true, value: size });
  return file;
}

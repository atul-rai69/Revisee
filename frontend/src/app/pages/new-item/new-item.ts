import {ChangeDetectorRef, Component,ElementRef,OnDestroy,OnInit,ViewChild, signal} from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import {FormBuilder,FormGroup,ReactiveFormsModule,Validators} from '@angular/forms';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Editor } from '@tiptap/core';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import StarterKit from '@tiptap/starter-kit';
import { LabelService } from '../../core/services/label-service';
import { AICredential, AICredentialsService } from '../../core/services/ai-credentials.service';
import { finalize } from 'rxjs';


// to store the uploaded images
// each uploaded image will have the actual file and the preview url
interface UploadedImage {
  file: File;
  preview: string;
}

// to store pdfs
interface UploadedPdf {
  file: File;
}

//to store labels with there id's
interface Label {
  id: number;
  user_id: number;
  label_name: string;
}

export const MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024;
export const MAX_PDF_UPLOAD_BYTES = 10 * 1024 * 1024;


@Component({
  selector: 'app-new-item',

  standalone: true,

  imports: [
    ReactiveFormsModule,
    CommonModule,
    FormsModule
  ],

  templateUrl: './new-item.html',

  styleUrls: ['./new-item.css', './new-item-generation.css'],
})


export class NewItem implements OnInit, OnDestroy {

  readonly maxImageUploadMegabytes = MAX_IMAGE_UPLOAD_BYTES / 1024 / 1024;
  readonly maxPdfUploadMegabytes = MAX_PDF_UPLOAD_BYTES / 1024 / 1024;

  @ViewChild('editorElement', { static: true })

  editorElement!: ElementRef;
  editor!: Editor;
  wordCount = 0;

  isDragging = false;

  learningItemForm!: FormGroup;
  
  // this will store all the uploaded images
  uploadedImages: UploadedImage[] = [];

  // to store uploaded pdfs
  uploadedPdfs: UploadedPdf[] = [];
  isPdfDragging = false;



  availableLabels: Label[] = [];



  selectedLabels: Label[] = [];

  labelSearch = '';
  readonly credentials = signal<AICredential[]>([]);
  readonly credentialsLoading = signal(false);
  readonly credentialsError = signal(false);
  readonly saving = signal(false);


  constructor(
    private fb: FormBuilder,
    private cdr: ChangeDetectorRef,
    private learningItem: LearningItem,
    private labelService: LabelService,
    private toaster: ToasterService,
    private credentialService: AICredentialsService,
  ) {}

  ngOnInit(): void {
    this.initializeForm();
    this.initializeEditor();
    this.getLabels();
    this.loadCredentials();
  }

  loadCredentials(): void {
    if (this.credentialsLoading()) return;
    this.credentialsLoading.set(true);
    this.credentialsError.set(false);
    this.credentialService.list().pipe(finalize(() => this.credentialsLoading.set(false))).subscribe({
      next: (response) => {
        this.credentials.set(response.credentials.filter((credential) => credential.status === 'VALID'));
        const selected = this.learningItemForm?.get('credentialId')?.value;
        if (!selected) {
          this.learningItemForm?.get('credentialId')?.setValue(
            response.credentials.find((credential) => credential.is_default && credential.status === 'VALID')?.id ?? null,
          );
        }
      },
      error: () => this.credentialsError.set(true),
    });
  }

  getLabels():void{
    this.labelService.getLabels().subscribe({

      next: (labels) => {
        this.availableLabels =labels;
        this.cdr.detectChanges();
        console.log(this.availableLabels);
      }

    });
  }


  onFileSelected(event: Event): void {

    const input =
      event.target as HTMLInputElement;

    if (!input.files) return;

    this.processFiles(input.files);
  }

  removeImage(index: number): void {

    this.uploadedImages.splice(index, 1);
  }

  // dragging events
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(): void {
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {

    event.preventDefault();

    this.isDragging = false;

    if (!event.dataTransfer?.files) return;

    this.processFiles(
      event.dataTransfer.files
    );
  }

  processFiles(files: FileList): void {
    this.acceptFilesWithinLimit(
      Array.from(files),
      MAX_IMAGE_UPLOAD_BYTES,
      'image',
    ).forEach(file => {

      const preview =
        URL.createObjectURL(file);

      this.uploadedImages.push({

        file,
        preview
      });
    });
  }


  // pdf upload methods
  onPdfSelected(event: Event): void {
    const input =
      event.target as HTMLInputElement;
    if (!input.files) return;

    this.processPdfFiles(input.files);
  }

  processPdfFiles(files: FileList): void {
    this.acceptFilesWithinLimit(
      Array.from(files),
      MAX_PDF_UPLOAD_BYTES,
      'PDF',
    ).forEach(file => {

      if (
        file.type !== 'application/pdf'
      ) {
        return;
      }

      this.uploadedPdfs.push({

        file
      });
    });
  }

  removePdf(index: number): void {

    this.uploadedPdfs.splice(index, 1);
  }

  onPdfDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isPdfDragging = true;
  }

  onPdfDragLeave(): void {
    this.isPdfDragging = false;
  }

  onPdfDrop(event: DragEvent): void {

    event.preventDefault();
    this.isPdfDragging = false;
    if (!event.dataTransfer?.files) return;
    this.processPdfFiles(
      event.dataTransfer.files
    );
  }


  // label methods
  // addLabel(label: string): void {

  //   if (
  //     this.selectedLabels.includes(label)
  //   ) {
  //     return;
  //   }

  //   this.selectedLabels.push(label);
  // }
  addLabel(label: Label): void {

    const exists = this.selectedLabels.some(
      selected => selected.id === label.id
    );

    if (exists) return;

    this.selectedLabels.push(label);
  }


  removeLabel(label: Label): void {

    this.selectedLabels =

      this.selectedLabels.filter(

        selected =>
          selected.id !== label.id
      );
  }



  initializeForm(): void {

    this.learningItemForm = this.fb.group({

      title: [
        '',
        [
          Validators.required,
          Validators.minLength(3)
        ]
      ],
      description_text: [
        '',
        [
          Validators.required
        ]
      ],
      generationSource: ['REVISEE'],
      credentialId: [null as number | null],
      personalRemarks: ['', [Validators.maxLength(2000)]],

    });
  }

  initializeEditor(): void {

    this.editor = new Editor({

      element:
        this.editorElement.nativeElement,

      extensions: [
        StarterKit
      ],

      content: '',

      editorProps: {

        attributes: {

          class: 'ProseMirror',

          placeholder:
            'Start typing your notes here...'
        }
      },

      onUpdate: ({ editor }) => {

        const text = editor.getText();

        this.wordCount = text.trim().split(/\s+/).filter(word => word.length > 0).length;

        this.descriptionTextControl.setValue(
          editor.getHTML(),
          { emitEvent: false }
        );

        // this.notesControl.markAsDirty();
        this.descriptionTextControl.markAsDirty();
      }
    });
  }

  toggleBold(): void {

    this.editor.chain().focus().toggleBold().run();
  }

  toggleItalic(): void {

    this.editor.chain().focus().toggleItalic().run();
  }

  toggleUnderline(): void {

    // Requires underline extension later
  }

  toggleBulletList(): void {

    this.editor
      .chain()
      .focus()
      .toggleBulletList()
      .run();
  }

  toggleOrderedList(): void {

    this.editor
      .chain()
      .focus()
      .toggleOrderedList()
      .run();
  }

  undo(): void {

    this.editor.chain().focus().undo().run();
  }

  redo(): void {

    this.editor.chain().focus().redo().run();
  }

  get notesControl() {

    return this.learningItemForm.get('notes')!;
  }

  get descriptionTextControl() {

    return this.learningItemForm.get(
      'description_text'
    )!;
  }



  // reset function
  resetFormState(): void {

    console.log('reset running');
    // reset reactive form
    this.learningItemForm.reset();
    this.learningItemForm.patchValue({
      generationSource: 'REVISEE',
      credentialId: this.credentials().find((credential) => credential.is_default)?.id ?? null,
      personalRemarks: '',
    });

    // clear uploaded images
    this.uploadedImages.forEach(image => {

      URL.revokeObjectURL(
        image.preview
      );

    });

    this.uploadedImages = [];

    // clear uploaded pdfs
    this.uploadedPdfs = [];

    // clear selected labels
    this.selectedLabels = [];

    // clear label search
    this.labelSearch = '';

    // reset word count
    this.wordCount = 0;

    // clear editor
    this.editor.commands.setContent('');

  }



  onSubmit(): void {
    if (this.saving()) return;
    
    if (
      this.learningItemForm.invalid
    ) {

      this.learningItemForm.markAllAsTouched();
      this.toaster.warning(
        'Please complete the required fields before saving.'
      );

      return;
    }

    if (
      this.learningItemForm.value.generationSource === 'PERSONAL'
      && !this.learningItemForm.value.credentialId
    ) {
      this.toaster.warning('Choose a valid personal Gemini credential or use Revisee-provided generation.');
      return;
    }

    if (!this.uploadSizesAreValid()) return;

    const formData = new FormData();

    // text fields
    formData.append(
      'title',
      this.learningItemForm.value.title
    );

    formData.append(
      'description_text',
      this.learningItemForm.value.description_text
    );

    // labels
    const labelIds = this.selectedLabels.map(
      label => label.id
    );

    formData.append(
      'labels',
      JSON.stringify(labelIds)
    );
    formData.append('generation_source', this.learningItemForm.value.generationSource);
    if (this.learningItemForm.value.generationSource === 'PERSONAL') {
      formData.append('credential_id', String(this.learningItemForm.value.credentialId));
      const remarks = this.learningItemForm.value.personalRemarks?.trim();
      if (remarks) formData.append('personal_remarks', remarks);
    }

    // images
    this.uploadedImages.forEach(image => {

      formData.append(
        'images',
        image.file
      );

    });

    // pdfs
    this.uploadedPdfs.forEach(pdf => {

      formData.append(
        'pdfs',
        pdf.file
      );

    });


    this.saving.set(true);
    this.learningItem.createLearningItem(formData).pipe(
      finalize(() => this.saving.set(false)),
    ).subscribe({

      next: (response) => {
        console.log(response);
        this.resetFormState();
        this.toaster.success(
          'Learning item created successfully.'
        );
      },
      error: (error: HttpErrorResponse) => {
        this.toaster.error(
          this.generationErrorMessage(error)
        );
      }

    });
  }



  ngOnDestroy(): void {

    this.editor.destroy();
  }

  get topicTitle() {

    return this.learningItemForm.get('title')!;
  }

  get generationSourceControl() {
    return this.learningItemForm.get('generationSource')!;
  }

  private generationErrorMessage(error: HttpErrorResponse): string {
    const detail = error.error?.detail;
    if (
      error.status === 422
      && typeof detail === 'string'
      && (detail.includes('image must be') || detail.includes('PDF must be'))
    ) return detail;
    if (error.status === 422) return 'The selected Gemini key or learning material was rejected. Check the credential and input limits.';
    if (error.status === 429) return 'Gemini quota or request limits were reached. Choose another option or try later.';
    if (error.status === 502) return 'Gemini returned content Revisee could not safely validate. Nothing was saved.';
    if (error.status === 503) return 'The selected generation provider is temporarily unavailable. Nothing was saved.';
    return 'Could not create the learning item. Nothing was saved; please try again.';
  }

  private acceptFilesWithinLimit(
    files: File[],
    maximumBytes: number,
    mediaLabel: 'image' | 'PDF',
  ): File[] {
    const accepted = files.filter((file) => file.size <= maximumBytes);
    const rejectedCount = files.length - accepted.length;
    if (rejectedCount) {
      const limit = maximumBytes / 1024 / 1024;
      this.toaster.warning(
        rejectedCount === 1
          ? `That ${mediaLabel} is larger than ${limit} MB and was not added.`
          : `${rejectedCount} ${mediaLabel} files are larger than ${limit} MB and were not added.`,
      );
    }
    return accepted;
  }

  private uploadSizesAreValid(): boolean {
    const oversizedImages = this.uploadedImages.some(
      ({ file }) => file.size > MAX_IMAGE_UPLOAD_BYTES,
    );
    const oversizedPdfs = this.uploadedPdfs.some(
      ({ file }) => file.size > MAX_PDF_UPLOAD_BYTES,
    );
    if (!oversizedImages && !oversizedPdfs) return true;
    this.toaster.warning(
      'Remove files larger than 10 MB before creating this learning item.',
    );
    return false;
  }

}

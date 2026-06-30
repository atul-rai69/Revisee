import {ChangeDetectorRef, Component,ElementRef,OnDestroy,OnInit,ViewChild} from '@angular/core';
import {FormBuilder,FormGroup,ReactiveFormsModule,Validators} from '@angular/forms';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { Editor } from '@tiptap/core';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import StarterKit from '@tiptap/starter-kit';
import { LabelService } from '../../core/services/label-service';


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


@Component({
  selector: 'app-new-item',

  standalone: true,

  imports: [
    ReactiveFormsModule,
    CommonModule,
    FormsModule
  ],

  templateUrl: './new-item.html',

  styleUrl: './new-item.css',
})


export class NewItem implements OnInit {

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


  constructor(
    private fb: FormBuilder,
    private cdr: ChangeDetectorRef,
    private learningItem: LearningItem,
    private labelService: LabelService,
    private toaster: ToasterService
  ) {}

  ngOnInit(): void {

    this.getLabels();

    this.initializeForm();
    this.initializeEditor();
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

    Array.from(files).forEach(file => {

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
    Array.from(files).forEach(file => {

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
      ]

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

    console.log(this.learningItemForm.value.title)
    
    if (
      this.learningItemForm.invalid
    ) {

      this.learningItemForm.markAllAsTouched();
      this.toaster.warning(
        'Please complete the required fields before saving.'
      );

      return;
    }

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


    this.learningItem.createLearningItem(formData).subscribe({

      next: (response) => {
        console.log(response);
        this.resetFormState();
        this.toaster.success(
          'Learning item created successfully.'
        );
      },
      error: (error) => {
        console.error(error);
        this.toaster.error(
          'Could not create the learning item. Please try again.'
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

}

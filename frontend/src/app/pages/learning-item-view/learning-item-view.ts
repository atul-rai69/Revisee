import { CommonModule } from '@angular/common';
import { Component, OnInit, signal, HostListener, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';


interface LearningItemResource {
  name: string;
  size: string;
}

interface LearningItemNote {
  title: string;
  meta: string;
  preview: string;
}

interface LearningItemQuestionOption {
  label: string;
  text: string;
  isCorrect: boolean;
}

interface LearningItemQuestion {
  number: number;
  question: string;
  options: LearningItemQuestionOption[];
}

@Component({
  selector: 'app-learning-item-view',
  imports: [
    CommonModule,
    RouterLink
  ],
  templateUrl: './learning-item-view.html',
  styleUrl: './learning-item-view.css',
})
export class LearningItemView implements OnInit {
  learningItemId = signal<string | null>(null);

  isLoading= false;

  topicTitle = "cell Structure";
  topicDescription = "Key components of a cell and their functions with a detailed explanation."
  imageCount = 1;
  pdfCount= 1;
  questionCount = 5;
  created_at = "2026-05-26T15:36:09"
  updated_at = "2026-05-26T15:36:09"
  img_url = "https://images.unsplash.com/photo-1532187643603-ba119ca4109e?auto=format&fit=crop&w=160&q=80"
  theory = "..."

  labels = [
    'Biology',
    'Cell Biology',
    'Class 11'
  ];


  keyPoints: string[] = [];

  resources: LearningItemResource[] = [
    {
      name: 'Cell Structure Notes.pdf',
      size: '1.2 MB',
    },
  ];

  notes: LearningItemNote[] = [
    {
      title: 'General Notes',
      meta: '12 May 2024 - 245 words',
      preview: 'The cell membrane is selectively permeable, allowing certain substances to pass while...',
    },
    {
      title: 'Important Definitions',
      meta: '18 May 2024 - 128 words',
      preview: 'Organelles are specialized structures within a cell that perform specific functions...',
    },
  ];

  questions: LearningItemQuestion[] = [
    {
      number: 1,
      question: 'What is the powerhouse of the cell?',
      options: [
        {
          label: 'A',
          text: 'Nucleus',
          isCorrect: false,
        },
        {
          label: 'B',
          text: 'Mitochondria',
          isCorrect: true,
        },
        {
          label: 'C',
          text: 'Ribosome',
          isCorrect: false,
        },
        {
          label: 'D',
          text: 'Golgi Apparatus',
          isCorrect: false,
        },
      ],
    },
  ];

  constructor(private learningItemService: LearningItem, private toaster: ToasterService, private route: ActivatedRoute,
        private cdr: ChangeDetectorRef
  ){}

  ngOnInit(): void {

    const itemId = Number(
      this.route.snapshot.paramMap.get('id')
    );

    this.learningItemService.getLearningItem(itemId).subscribe({
      next: (response) => {
        console.log("response = ", response.data);
        this.topicTitle = response.data.title
        this.topicDescription = this.stripHtml(response.data.description_text) 
        this.created_at = response.data.created_at
        this.updated_at = response.data.updated_at
        this.imageCount = response.data.image_count
        this.pdfCount = response.data.pdf_count
        this.theory = response.data.theory?? ""
        this.img_url = response.data.first_image_url
        this.keyPoints = response.data.key_points
        this.questions = response.data.questions
        this.labels = response.data.labels? response.data.labels.split(',').map((label: string) => label.trim()): []
        this.img_urls = response.data.image_urls? response.data.image_urls.split(',').map((url: string) => url.trim()): []
        this.cdr.detectChanges()
      },
      error: (err) => {
        console.error(err);
      }
    });

  }

  generate(){
    this.learningItemService.getAicontent(this.topicTitle, this.topicDescription).subscribe({
      next: (response) => {
        console.log("response = ", response);
        this.theory = response.data.theory;
      },
      error: (err) => {
        console.error(err);
      }
    });
  }


  check(){
    alert('change detection fired');
  }
  
  private stripHtml(html: string): string {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || '';
  }


  // image gallery code
  images = [
    {
      title: 'Cell Structure',
      url: 'https://images.unsplash.com/photo-1596495578065-6e0763fa1178?auto=format&fit=crop&w=160&q=80'
    },
    {
      title: 'Nucleus',
      url: 'https://images.unsplash.com/photo-1532187643603-ba119ca4109e?auto=format&fit=crop&w=160&q=80'
    },
    {
      title: 'Cell Membrane',
      url: 'https://images.unsplash.com/photo-1596495578065-6e0763fa1178?auto=format&fit=crop&w=160&q=80'
    },
    {
      title: 'Mitochondria',
      url: 'https://images.unsplash.com/photo-1501004318641-b39e6451bec6?auto=format&fit=crop&w=160&q=80'
    },
    {
      title: 'Golgi Apparatus',
      url: 'https://images.unsplash.com/photo-1607988795691-3d0147b43231?auto=format&fit=crop&w=160&q=80'
    },
    {
      title: 'Lysosome',
      url: 'https://images.unsplash.com/photo-1596495578065-6e0763fa1178?auto=format&fit=crop&w=160&q=80'
    }
  ];

  img_urls = [
    'https://images.unsplash.com/photo-1596495578065-6e0763fa1178?auto=format&fit=crop&w=160&q=80',
    'https://images.unsplash.com/photo-1532187643603-ba119ca4109e?auto=format&fit=crop&w=160&q=80',
    'https://images.unsplash.com/photo-1596495578065-6e0763fa1178?auto=format&fit=crop&w=160&q=80'
  ]

  lightboxOpen = false;

  currentIndex = 0;

  openLightbox(index: number): void {
    this.currentIndex = index;
    this.lightboxOpen = true;

    document.body.style.overflow = 'hidden';
  }

  closeLightbox(): void {
    this.lightboxOpen = false;

    document.body.style.overflow = 'auto';
  }

  selectImage(index: number): void {
    this.currentIndex = index;
  }

  nextImage(): void {
    this.currentIndex =
      (this.currentIndex + 1) %
      this.img_urls.length;
  }

  previousImage(): void {
    this.currentIndex =
      (this.currentIndex - 1 + this.img_urls.length) %
      this.img_urls.length;
  }

  downloadImage(): void {
    const link = document.createElement('a');

    link.href = this.images[this.currentIndex].url;

    link.download =
      this.images[this.currentIndex].title;

    link.click();
  }

  @HostListener('document:keydown.escape')
  handleEscape(): void {
    if (this.lightboxOpen) {
      this.closeLightbox();
    }
  }

  @HostListener('document:keydown.arrowright')
  handleRight(): void {
    if (this.lightboxOpen) {
      this.nextImage();
    }
  }

  @HostListener('document:keydown.arrowleft')
  handleLeft(): void {
    if (this.lightboxOpen) {
      this.previousImage();
    }
  }
}

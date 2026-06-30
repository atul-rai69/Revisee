import {
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild
} from '@angular/core';
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';

@Component({
  selector: 'app-design-preview',
  imports: [],
  templateUrl: './design-preview.html',
  styleUrl: './design-preview.css',
})
export class DesignPreview {

  @ViewChild('editorElement', { static: true })

    editorElement!: ElementRef;
    editor!: Editor;

    ngOnInit(): void {

      

      this.initializeEditor();
    }

    initializeEditor(): void {

      this.editor = new Editor({

        element:
          this.editorElement.nativeElement,

        extensions: [
          StarterKit
        ],

        content: `
          <p>
            Start writing your revision notes...
          </p>
        `
      });
    }

    ngOnDestroy(): void {

      this.editor.destroy();
    }
}

import { Component, OnInit, computed, signal } from '@angular/core';

import {
  FormBuilder,
  FormGroup,
  Validators,
  ReactiveFormsModule
} from '@angular/forms';

import { CommonModule } from '@angular/common';
import { Label, LabelService } from '../../core/services/label-service';
import { ToasterService } from '../../core/services/toaster.service';

@Component({
  selector: 'app-labels',
  imports: [
    CommonModule,
    ReactiveFormsModule
  ],
  templateUrl: './labels.html',
  styleUrl: './labels.css',
})
export class Labels implements OnInit {
  labelForm!: FormGroup;

  // Signal state tells Angular to update the UI as soon as the value changes.
  labels = signal<Label[]>([]);
  editingLabelId = signal<number | null>(null);

  searchTerm = '';

  // Search stays hard-coded/unwired for now, so this returns all labels.
  filteredLabels = computed(() => this.labels());

  constructor(

    private fb: FormBuilder,
    private labelService: LabelService,
    private toaster: ToasterService

  ) {}

  ngOnInit(): void {

    this.initializeForm();
    this.loadLabels();
  }

  // Keep form setup in one place so create and edit can reuse it safely.
  initializeForm(): void {

    this.labelForm = this.fb.group({

      labelName: [

        '',

        [
          Validators.required,
          Validators.minLength(2)
        ]
      ]
    });
  }

  // Fetch the user's labels from the backend.
  loadLabels(): void {

    this.labelService.getLabels().subscribe({
      next: (labels) => {
        // set() replaces the signal value and triggers a template refresh.
        this.labels.set(labels);
      },
      error: (error) => {
        console.error(error);
        this.toaster.error('Could not load Topics.');
      }
    });
  }

  onCreateLabel(): void {

    if (
      this.labelForm.invalid
    ) {
      this.labelForm.markAllAsTouched();

      return;
    }

    const labelName =
      this.labelForm.value.labelName.trim();

    const editingId = this.editingLabelId();

    if (editingId) {
      this.updateLabel(
        editingId,
        labelName
      );

      return;
    }

    this.createLabel(labelName);
  }

  // Send POST request for a new label.
  createLabel(labelName: string): void {

    this.labelService.createLabel(labelName).subscribe({
      next: () => {
        this.toaster.success('Topic created successfully.');
        this.resetForm();
        this.loadLabels();
      },
      error: (error) => {
        console.error(error);
        this.toaster.error('Could not create Topic.');
      }
    });
  }

  // Send PATCH request when an existing label is being edited.
  updateLabel(
    id: number,
    labelName: string
  ): void {

    this.labelService.updateLabel(id, labelName).subscribe({
      next: () => {
        this.toaster.success('Topic updated successfully.');
        this.resetForm();
        this.loadLabels();
      },
      error: (error) => {
        console.error(error);
        this.toaster.error('Could not update Topic.');
      }
    });
  }

  // Put the selected label into the form and switch to edit mode.
  onEditLabel(label: Label): void {

    // Store the selected id in a signal so the form title/buttons update.
    this.editingLabelId.set(label.id);

    this.labelForm.patchValue({
      labelName: label.label_name
    });
  }

  // Clear edit mode and reset form values.
  resetForm(): void {

    // Resetting the signal switches the form back to create mode.
    this.editingLabelId.set(null);
    this.labelForm.reset();
  }
}

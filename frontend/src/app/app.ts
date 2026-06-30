import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ToastContainer } from './shared/components/toast-container/toast-container';
import { Loader } from './shared/components/loader/loader';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    Loader,
    ToastContainer
  ],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected readonly title = signal('frontend');
}

import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { Router } from '@angular/router';
import { ToasterService } from '../../core/services/toaster.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
   username = '';
  password = '';

  constructor(private authService: AuthService, private router: Router,private toaster: ToasterService ) {}

  onLogin() {

    this.authService
    .login(this.username, this.password)
    .subscribe({

      next: (response: any) => {

        console.log(response);

        localStorage.setItem(
          'token',
          response.access_token
        );

        this.toaster.success(
          'Logged in successfully'
        );

        this.router.navigate(['app/dashboard'])
      },

      error: (error) => {
        console.log(error);
        this.toaster.error(
          'Invalid Credentials'
        );
      }

    });
  }
}

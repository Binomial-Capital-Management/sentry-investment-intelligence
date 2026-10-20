/**
 * Form validation utilities for auth forms
 */

import { VALIDATION_PATTERNS, VALIDATION_CONSTRAINTS } from '../constants';

// Identifier validation (email or username)
export function validateIdentifier(value: string): string {
  if (!value) {
    return 'Email or username is required';
  }
  
  const isEmail = VALIDATION_PATTERNS.EMAIL.test(value);
  const isUsername = VALIDATION_PATTERNS.USERNAME.test(value);
  
  if (!isEmail && !isUsername) {
    return 'Enter a valid email or username';
  }
  
  return '';
}

// Email validation
export function validateEmail(value: string): string {
  if (!value) {
    return 'Email is required';
  }
  
  if (!VALIDATION_PATTERNS.EMAIL.test(value)) {
    return 'Invalid email format';
  }
  
  return '';
}

// Password validation
export function validatePassword(value: string): string {
  if (!value) {
    return 'Password is required';
  }
  
  if (value.length < VALIDATION_CONSTRAINTS.PASSWORD_MIN_LENGTH) {
    return `Password must be at least ${VALIDATION_CONSTRAINTS.PASSWORD_MIN_LENGTH} characters`;
  }
  
  return '';
}

// Confirm password validation
export function validateConfirmPassword(value: string, password: string): string {
  if (!value) {
    return 'Please confirm your password';
  }
  
  if (value !== password) {
    return 'Passwords do not match';
  }
  
  return '';
}

// First name validation
export function validateFirstName(value: string): string {
  if (!value) {
    return 'First name is required';
  }
  
  if (value.length < VALIDATION_CONSTRAINTS.NAME_MIN_LENGTH) {
    return `First name must be at least ${VALIDATION_CONSTRAINTS.NAME_MIN_LENGTH} characters`;
  }
  
  return '';
}

// Last name validation
export function validateLastName(value: string): string {
  if (!value) {
    return 'Last name is required';
  }
  
  if (value.length < VALIDATION_CONSTRAINTS.NAME_MIN_LENGTH) {
    return `Last name must be at least ${VALIDATION_CONSTRAINTS.NAME_MIN_LENGTH} characters`;
  }
  
  return '';
}

// Username validation
export function validateUsername(value: string): string {
  if (!value) {
    return 'Username is required';
  }
  
  if (value.length < VALIDATION_CONSTRAINTS.USERNAME_MIN_LENGTH) {
    return `Username must be at least ${VALIDATION_CONSTRAINTS.USERNAME_MIN_LENGTH} characters`;
  }
  
  if (!VALIDATION_PATTERNS.USERNAME.test(value)) {
    return 'Username can only contain letters, numbers, and underscores';
  }
  
  return '';
}

// Verification code validation
export function validateVerificationCode(value: string): string {
  if (!value) {
    return 'Verification code is required';
  }
  
  if (value.length !== VALIDATION_CONSTRAINTS.VERIFICATION_CODE_LENGTH) {
    return `Please enter the ${VALIDATION_CONSTRAINTS.VERIFICATION_CODE_LENGTH}-digit code from your email`;
  }
  
  return '';
}

// Helper to check if form has errors
export function hasErrors(errors: Record<string, string>): boolean {
  return Object.values(errors).some(error => error !== '');
}

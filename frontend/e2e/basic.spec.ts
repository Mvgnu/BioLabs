import { test, expect } from '@playwright/test';

const user = {
  email: 'testuser@example.com',
  password: 'password123'
};

test('register and login', async ({ page }) => {
  await page.goto('/register');
  await page.getByPlaceholder('Email').fill(user.email);
  await page.getByPlaceholder('Password').fill(user.password);
  await page.click('button[type="submit"]');
  await page.waitForURL('/');
  await page.click('text=Logout');

  await page.goto('/login');
  await page.getByPlaceholder('Email').fill(user.email);
  await page.getByPlaceholder('Password').fill(user.password);
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/');
});

// Shared sign-in for the browser walkthroughs: the demo user created by `python -m backend.app.seed_demo`.
export const credentials = {
  email: process.env.SCOREMASTER_USER || 'demo@scoremaster.local',
  password: process.env.SCOREMASTER_PASSWORD || 'scoremaster-demo',
};

export async function login(page, { email, password } = credentials) {
  await page.locator('#login-email').fill(email);
  await page.locator('#login-password').fill(password);
  await page.locator('#login-submit').click();
  await page.locator('#app-shell').waitFor({ state: 'visible' });
}

// CSRF token of the signed-in page, for walkthroughs that call the API directly.
export async function csrfToken(page, url) {
  return (await (await page.request.get(url + '/auth/me')).json()).csrf_token;
}

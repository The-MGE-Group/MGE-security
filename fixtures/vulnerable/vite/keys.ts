// Deliberately vulnerable. Test fixture only (a Vite browser app).
// Planted problem: a secret exposed to the browser through a VITE_ name.
export const stripe = import.meta.env.VITE_STRIPE_SECRET_KEY;

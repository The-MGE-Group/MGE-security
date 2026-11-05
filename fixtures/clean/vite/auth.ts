// Clean test fixture: a Vite browser app. Only public values in VITE_, and getSession() in the browser is fine.
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_ANON_KEY);

export async function token() {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token;
}

"use client";
// Clean test fixture: browser code uses the public anon key and getSession() (fine in the browser).
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!);

export async function signedIn() {
  const { data } = await supabase.auth.getSession();
  return Boolean(data.session);
}

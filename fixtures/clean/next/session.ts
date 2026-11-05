// Clean test fixture: public values only in NEXT_PUBLIC_, and getUser() on the server.
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!);

export async function currentUserId() {
  const { data } = await supabase.auth.getUser();
  return data.user?.id;
}

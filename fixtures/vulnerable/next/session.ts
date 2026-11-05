// Deliberately vulnerable. Test fixture only.
import { createClient } from "@supabase/supabase-js";

// Planted problem: a secret exposed to the browser through a NEXT_PUBLIC_ name.
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY!);

export async function currentUserId() {
  // Planted problem: trusting getSession() on the server.
  const { data } = await supabase.auth.getSession();
  return data.session?.user.id;
}

// Deliberately vulnerable. Test fixture only.
import { createClient } from "@supabase/supabase-js";

// Planted problem: a secret exposed to the browser through a NEXT_PUBLIC_ name.
export const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY!);

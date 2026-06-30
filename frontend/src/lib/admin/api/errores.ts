import { authedJson } from "@/lib/authedFetch";

export type ServerError = {
  id: number;
  route: string;
  error_type: string;
  message: string;
  traceback: string;
  request_id: string | null;
  created_at: string;
};

export type ServerErrorsResp = {
  errores: ServerError[];
  total: number;
};

export const erroresMethods = {
  listServerErrors: (limite = 200) =>
    authedJson<ServerErrorsResp>(`/api/admin/server-errors?limite=${limite}`),
};

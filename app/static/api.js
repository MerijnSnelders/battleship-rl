// Thin wrapper around the game API described in docs/api.md.

export class ApiError extends Error {
  constructor(code, detail, status) {
    super(detail);
    this.code = code;
    this.status = status;
  }
}

async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError("network", "Could not reach the server.", 0);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(data?.error ?? "unknown", data?.detail ?? response.statusText, response.status);
  }
  return data;
}

const game = (id) => `/api/games/${encodeURIComponent(id)}`;

export const api = {
  opponents: () => request("GET", "/api/opponents"),
  newGame: (opponent, config) => request("POST", "/api/games", { opponent, config }),
  getGame: (id) => request("GET", game(id)),
  place: (id, start, length, orientation) =>
    request("POST", `${game(id)}/ships`, { start, length, orientation }),
  remove: (id, [row, col]) => request("DELETE", `${game(id)}/ships?row=${row}&col=${col}`),
  clear: (id) => request("DELETE", `${game(id)}/ships`),
  randomFleet: (id) => request("POST", `${game(id)}/ships/random`),
  start: (id) => request("POST", `${game(id)}/start`),
  fire: (id, row, col) => request("POST", `${game(id)}/fire`, { row, col }),
};

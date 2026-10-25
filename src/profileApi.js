// The profile API must return JSON. A transient upstream HTML page must never
// be presented as a JSON syntax error or mistaken for a successful save.
export async function profileJson(response, action = 'atualizar o perfil') {
  const type = (response.headers?.get('content-type') || '').toLowerCase();
  if (!type.includes('application/json')) {
    console.warn('JH_PROFILE_API_UNEXPECTED_RESPONSE', {
      status: response.status,
      contentType: type.slice(0, 100),
      redirected: response.redirected === true,
    });
    const error = new Error(
      `Não foi possível ${action}: o servidor retornou uma página em vez de JSON (HTTP ${response.status}). Seus dados continuam nesta tela; tente novamente em instantes.`
    );
    error.code = 'PROFILE_NON_JSON';
    throw error;
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`A resposta ao tentar ${action} estava incompleta. Seus dados continuam nesta tela; tente novamente.`);
  }
  if (!response.ok) {
    if (response.status === 401) throw new Error('Sua sessão expirou. Entre novamente antes de salvar o perfil.');
    const detail = typeof data?.detail === 'string' ? data.detail : `Falha ao ${action} (HTTP ${response.status})`;
    throw new Error(detail);
  }
  return data;
}

export async function saveProfileRequest(profile, request = fetch) {
  // PUT is idempotent. A single retry handles a transient HTML gateway page
  // during a deployment without introducing a second update mechanism.
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await request('/api/profile', {
      method: 'PUT',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ profile }),
    });
    try {
      return await profileJson(response, 'salvar suas experiências');
    } catch (error) {
      if (error.code !== 'PROFILE_NON_JSON' || attempt === 1) throw error;
    }
  }
}

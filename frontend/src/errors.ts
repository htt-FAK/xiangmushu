type ApiErrorDetail = {
  reason?: string;
  message?: string;
};

type ApiErrorPayload = {
  message?: string;
  detail?: string | ApiErrorDetail;
};

const AUTH_REASON_MESSAGES: Record<string, string> = {
  invalid_credentials: "邮箱或密码不正确",
  invalid_email: "请输入有效的邮箱地址",
  invalid_password: "密码不正确或不符合要求",
  email_exists: "该邮箱已注册，请直接登录",
  email_not_found: "该邮箱尚未注册，请先创建账号",
  account_unverified: "该账号尚未完成邮箱验证，请继续验证",
  account_restricted: "该账号当前无法继续登录，请联系管理员",
  challenge_expired: "验证码已过期，请重新发送",
  challenge_superseded: "旧验证码已失效，请使用最新验证码",
  challenge_consumed: "验证码已被使用，请重新发送",
  invalid_code: "验证码不正确，请检查后重试",
  invalid_recovery_token: "重置凭证无效或已过期，请重新发起重置",
  rate_limited: "操作过于频繁，请稍后再试",
  auth_error: "认证失败，请稍后重试",
  request_blocked: "请求暂时无法继续，请检查配置后重试",
};

const EXACT_MESSAGE_TRANSLATIONS: Record<string, string> = {
  "Authentication required": "请先登录",
  "Admin access required": "需要管理员权限",
  "Download failed": "下载失败，请稍后重试",
  "Email or password is incorrect": "邮箱或密码不正确",
  "Password is required": "请输入密码",
  "Session expired": "登录已过期，请重新登录",
  "Strict BYOK is enabled. Please save your own API Key in Settings before analyzing templates or generating content.":
    "请先在设置页保存你自己的 API Key，然后再进行模板分析或内容生成。",
};

function translateMessage(message: string, reason?: string): string {
  const trimmed = message.trim().replace(/^\d{3}:\s*/, "");
  if (EXACT_MESSAGE_TRANSLATIONS[trimmed]) return EXACT_MESSAGE_TRANSLATIONS[trimmed];
  if (reason === "invalid_password" && /email or password/i.test(trimmed)) {
    return "邮箱或密码不正确";
  }
  if (reason && AUTH_REASON_MESSAGES[reason]) return AUTH_REASON_MESSAGES[reason];
  return trimmed;
}

export function parseApiErrorMessage(raw: string, fallback: string): string {
  let message = raw || fallback;
  let reason = "";
  try {
    const parsed = JSON.parse(raw) as ApiErrorPayload;
    if (typeof parsed.detail === "string") {
      message = parsed.detail;
    } else if (parsed.detail) {
      reason = parsed.detail.reason ?? "";
      message = parsed.detail.message ?? "";
    } else if (parsed.message) {
      message = parsed.message;
    }
  } catch {
    // Keep the raw response when the server did not return JSON.
  }
  return translateMessage(message || fallback, reason);
}

export function normalizeErrorMessage(value: unknown, fallback: string): string {
  if (value instanceof Error) {
    return parseApiErrorMessage(value.message, fallback);
  }
  if (typeof value === "string") {
    return parseApiErrorMessage(value, fallback);
  }
  return fallback;
}

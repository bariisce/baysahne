import { AuthLayout } from "@/components/AuthLayout";
import { LoginForm } from "@/components/LoginForm";

export default function LoginPage() {
  return (
    <AuthLayout title="Yönetim paneli" lead="Bay Sahne içerik yönetimine giriş yapın.">
      <LoginForm />
      <p className="small muted" style={{ textAlign: "center", marginBottom: 0 }}>
        Hesaplar yalnızca davetle açılır. Erişime ihtiyacınız varsa yöneticinize başvurun.
      </p>
    </AuthLayout>
  );
}

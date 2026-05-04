import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Legacy marketing JSX (Dashboard, AgentPage, …) has many ESLint violations; typecheck still runs.
  eslint: { ignoreDuringBuilds: true },
  allowedDevOrigins: ["192.168.56.1"],
  experimental: {
    optimizePackageImports: ["framer-motion", "lucide-react"],
  },
};

export default nextConfig;

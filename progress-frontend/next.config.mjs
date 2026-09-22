/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return {
      // The landing is a static page (public/landing), served at the root.
      beforeFiles: [{ source: "/", destination: "/landing/index.html" }],
    };
  },
};
export default nextConfig;

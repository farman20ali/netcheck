class Netcheck < Formula
  include Language::Python::Virtualenv

  desc "Lightweight network connectivity checker — TCP, DNS, HTTP, SSL, ping, traceroute, WHOIS"
  homepage "https://github.com/farman20ali/netcheck"
  url "https://files.pythonhosted.org/packages/source/n/netcheckx/netcheckx-2.4.0.tar.gz"
  sha256 "6d7f023d8c1c4e7a85854728562325c7e145e69e2c65a7e58c0c4e7a8585472a" # Placeholder or release SHA256
  license "GPL-3.0-only"
  head "https://github.com/farman20ali/netcheck.git", branch: "main"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/netcheck", "--version"
    system "#{bin}/netcheck", "dns", "google.com"
  end
end

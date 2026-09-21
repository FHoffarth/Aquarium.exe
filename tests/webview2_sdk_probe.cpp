#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <unknwn.h>
#include <WebView2.h>

#include <iostream>

int wmain() {
  LPWSTR version = nullptr;
  const HRESULT result = GetAvailableCoreWebView2BrowserVersionString(nullptr, &version);
  if (FAILED(result) || !version) {
    std::wcerr << L"FAIL: WebView2 Runtime unavailable, HRESULT=0x" << std::hex << result << L"\n";
    return 1;
  }
  std::wcout << L"PASS: WebView2 Runtime " << version << L"\n";
  CoTaskMemFree(version);
  return 0;
}

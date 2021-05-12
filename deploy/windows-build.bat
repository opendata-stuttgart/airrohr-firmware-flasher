cd %~dp0\..

if not exist build mkdir build

rem Download python installer
if not exist build\python-installer.exe powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (new-object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.6.7/python-3.6.7-amd64.exe', 'build\python-installer.exe')"
if not exist %LocalAppData%\Programs\Python\Python36 build\python-installer.exe InstallAllUsers=0 Include_launcher=0 Include_test=0 /passive

rem PATH is only reloaded on reboot/login, so we need to force it here
set PATH=%LocalAppData%\Programs\Python\Python36\;%LocalAppData%\Programs\Python\Python36\Scripts\;%LocalAppData%\Roaming\Python\Python36\;%LocalAppData%\Roaming\Python\Python36\Scripts\;%PATH%
copy %LocalAppData%\Programs\Python\Python36\python.exe %LocalAppData%\Programs\Python\Python36\python3.exe

rem Download cygwin installer
if not exist build\cygwin-x86.exe powershell -Command "(new-object System.Net.WebClient).DownloadFile('https://cygwin.com/setup-x86.exe', 'build\cygwin-x86.exe')"

rem Install required Cygwin packages
if not exist build\cygwin build\cygwin-x86.exe --site http://cygwin.mirror.constant.com ^
	--no-shortcuts ^
	--no-desktop ^
	--quiet-mode ^
	--root "%cd%\build\cygwin" ^
	--arch x86 ^
	--local-package-dir "%cd%\build\cygwin-packages" ^
	--verbose ^
	--prune-install ^
	--no-admin ^
	--packages qt5-linguist-tools,make

build\cygwin\bin\bash.exe --login -i -c "ln -s `which lrelease-qt5` /usr/bin/lrelease; cd \"%cd%\" && make deps dist"

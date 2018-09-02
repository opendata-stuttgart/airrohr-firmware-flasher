if not exist build mkdir build

rem Download cygwin installer
if not exist build\cygwin-x86.exe powershell -Command "Invoke-WebRequest https://cygwin.com/setup-x86.exe -OutFile build\cygwin-x86.exe"

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

build\cygwin\bin\bash.exe --login -i -c "ln -s `which lrelease-qt5` /usr/bin/lrelease ; cd \"%cd%\" && make deps dist"

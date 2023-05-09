@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem

@if "%DEBUG%" == "" @echo off
@rem ##########################################################################
@rem
@rem  examples startup script for Windows
@rem
@rem ##########################################################################

@rem Set local scope for the variables with windows NT shell
if "%OS%"=="Windows_NT" setlocal

set DIRNAME=%~dp0
if "%DIRNAME%" == "" set DIRNAME=.
set APP_BASE_NAME=%~n0
set APP_HOME=%DIRNAME%..

@rem Resolve any "." and ".." in APP_HOME to make it shorter.
for %%i in ("%APP_HOME%") do set APP_HOME=%%~fi

@rem Add default JVM options here. You can also use JAVA_OPTS and EXAMPLES_OPTS to pass JVM options to this script.
set DEFAULT_JVM_OPTS="-Xms512m" "-Xmx512m" "-Xlog:gc*:file=./gc_report.log"

@rem Find java.exe
if defined JAVA_HOME goto findJavaFromJavaHome

set JAVA_EXE=java.exe
%JAVA_EXE% -version >NUL 2>&1
if "%ERRORLEVEL%" == "0" goto init

echo.
echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:findJavaFromJavaHome
set JAVA_HOME=%JAVA_HOME:"=%
set JAVA_EXE=%JAVA_HOME%/bin/java.exe

if exist "%JAVA_EXE%" goto init

echo.
echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME%
echo.
echo Please set the JAVA_HOME variable in your environment to match the
echo location of your Java installation.

goto fail

:init
@rem Get command-line arguments, handling Windows variants

if not "%OS%" == "Windows_NT" goto win9xME_args

:win9xME_args
@rem Slurp the command line arguments.
set CMD_LINE_ARGS=
set _SKIP=2

:win9xME_args_slurp
if "x%~1" == "x" goto execute

set CMD_LINE_ARGS=%*

:execute
@rem Setup the command line

set CLASSPATH=%APP_HOME%\lib\examples.jar;%APP_HOME%\lib\picocli-4.3.2.jar;%APP_HOME%\lib\jmockets-1.2.jar;%APP_HOME%\lib\args4j-2.0.25.jar;%APP_HOME%\lib\logback-classic-1.2.3.jar;%APP_HOME%\lib\jutil-1.0.jar;%APP_HOME%\lib\jnats-1.0.jar;%APP_HOME%\lib\slf4j-api-1.7.25.jar;%APP_HOME%\lib\lombok-1.18.20.jar;%APP_HOME%\lib\grpc-1.0-SNAPSHOT.jar;%APP_HOME%\lib\grpc-protobuf-1.43.2.jar;%APP_HOME%\lib\grpc-stub-1.43.2.jar;%APP_HOME%\lib\grpc-netty-shaded-1.43.2.jar;%APP_HOME%\lib\grpc-protobuf-lite-1.43.2.jar;%APP_HOME%\lib\grpc-core-1.43.2.jar;%APP_HOME%\lib\grpc-api-1.43.2.jar;%APP_HOME%\lib\protobuf-java-util-3.1.0.jar;%APP_HOME%\lib\reflections-0.9.11.jar;%APP_HOME%\lib\guava-30.1.1-android.jar;%APP_HOME%\lib\bctls-jdk15on-1.70.jar;%APP_HOME%\lib\snakeyaml-1.8.jar;%APP_HOME%\lib\ipaddress-5.0.0.jar;%APP_HOME%\lib\bcpkix-jdk15on-1.66.jar;%APP_HOME%\lib\junit-4.12.jar;%APP_HOME%\lib\logback-core-1.2.3.jar;%APP_HOME%\lib\failureaccess-1.0.1.jar;%APP_HOME%\lib\listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.jar;%APP_HOME%\lib\jsr305-3.0.2.jar;%APP_HOME%\lib\error_prone_annotations-2.9.0.jar;%APP_HOME%\lib\j2objc-annotations-1.3.jar;%APP_HOME%\lib\animal-sniffer-annotations-1.19.jar;%APP_HOME%\lib\bcutil-jdk15on-1.70.jar;%APP_HOME%\lib\bcprov-jdk15on-1.70.jar;%APP_HOME%\lib\proto-google-common-protos-2.0.1.jar;%APP_HOME%\lib\measure.jar;%APP_HOME%\lib\protobuf-java-3.19.2.jar;%APP_HOME%\lib\Java-WebSocket-1.3.8.jar;%APP_HOME%\lib\commons-lang3-3.8.1.jar;%APP_HOME%\lib\cloning-1.9.3.jar;%APP_HOME%\lib\hamcrest-core-1.3.jar;%APP_HOME%\lib\perfmark-api-0.23.0.jar;%APP_HOME%\lib\checker-compat-qual-2.5.5.jar;%APP_HOME%\lib\grpc-context-1.43.2.jar;%APP_HOME%\lib\commons-math3-3.6.1.jar;%APP_HOME%\lib\gson-2.8.9.jar;%APP_HOME%\lib\javassist-3.21.0-GA.jar;%APP_HOME%\lib\objenesis-2.1.jar;%APP_HOME%\lib\annotations-4.1.1.4.jar


@rem Execute examples
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %EXAMPLES_OPTS%  -classpath "%CLASSPATH%" examples.congestion.CCTrainingServer %CMD_LINE_ARGS%

:end
@rem End local scope for the variables with windows NT shell
if "%ERRORLEVEL%"=="0" goto mainEnd

:fail
rem Set variable EXAMPLES_EXIT_CONSOLE if you need the _script_ return code instead of
rem the _cmd.exe /c_ return code!
if  not "" == "%EXAMPLES_EXIT_CONSOLE%" exit 1
exit /b 1

:mainEnd
if "%OS%"=="Windows_NT" endlocal

:omega

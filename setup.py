from setuptools import setup,find_packages

setup(
    name = "telebot",
    version = "0.1a1",
    packages = find_packages(),
    author = "Nicolas Limage",
    author_email = 'github@xephon.org',
    description = "telegram bot library",
    license = "MIT",
    keywords = "telegram bot",
    url = "https://github.com/nlm/telebot",
    classifiers = [
        'Development Status :: 1 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: MIT',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    install_requires = [
        'aiohttp',
    ]
)

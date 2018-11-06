from setuptools import setup, find_packages

setup(
    name="gitlab-simple",
    version="1.2",
    description="Simple GUI for managing GitLab projects",
    python_requires=">=3.6.1",
    classifiers=["Programming Language :: Python :: 3"],
    entry_points={"console_scripts": ["gitlabsimple=gitlabsimple.__main__:main"]},
    keywords="gitlab",
    url="https://github.com/plapadoo/gitlab-simple",
    author="plapadoo",
    author_email="info@plapadoo.de",
    license="License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    packages=find_packages(),
    install_requires=[
        "python-gitlab",
        "pyxdg",
        "terminaltables",
        "termcolor",
        "humanize",
        "python-dateutil",
        "consolemd",
    ],
    include_package_data=True,
    zip_safe=True,
)

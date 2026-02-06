from setuptools import setup, find_packages


requirements = [
    r.strip() for r in open('requirements.txt').readlines() if '#' not in r]


setup(
    name='gosuslugi-api',
    author='Greg Eremeev',
    author_email='gregory.eremeev@gmail.com',
    version='1.0.0',
    license='MIT',
    url='https://github.com/yasg1988/gosuslugi-api',
    install_requires=requirements,
    description='Toolset to work with dom.gosuslugi.ru public API',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    python_requires='>=3.8',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    zip_safe=False,
    include_package_data=True,
)

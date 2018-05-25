import setuptools
import codecs
import os.path

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    readme_file_contents = f.read()

setuptools.setup(
    name='greedy_string_tiling',
    version='0.1.0',
    description='C++ implementation of the Greedy String Tiling string matching algorithm.',
    long_description=readme_file_contents,

    author='Matias Lindgren',
    author_email='matias.lindgren@gmail.com',
    license='MIT',

    install_requires=[
        'hypothesis', # For testing the built module. Not strictly required but recommended.
    ],

    ext_modules=[
        setuptools.Extension(
            'gst',
            sources=['src/gstmodule.cpp', 'src/gst.cpp'],
            include_dirs=["include"],
            extra_compile_args=["--std=c++11"],
        ),
    ],
)


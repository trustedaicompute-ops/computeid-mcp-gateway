from setuptools import setup, find_packages

setup(
    name="computeid-mcp",
    version="1.2.0",
    description="ComputeID MCP Server — cryptographic identity for AI agents via Model Context Protocol",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="ComputeID",
    author_email="hello@compute-id.com",
    url="https://github.com/trustedaicompute-ops/computeid-mcp",
    py_modules=["server"],
    install_requires=[
        "mcp>=1.0.0,<2",  # server.py uses the 1.x low-level Server API (removed in 2.0)
        "httpx>=0.24.0",
    ],
    entry_points={
        "console_scripts": [
            "computeid-mcp=server:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Security :: Cryptography",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="mcp model-context-protocol ai agents identity security computeid",
)

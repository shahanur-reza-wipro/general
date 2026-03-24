docker run --rm -v ${PWD}:/lambda_build -w /lambda_build amazonlinux:2 \
/bin/bash -c "
    yum install -y python3-pip zip && \
    pip3 install requests -t ./package && \
    cd package && \
    zip -r9 ../lambda_function.zip .
"

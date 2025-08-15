import unittest
import json
import yaml
import boto3
import os
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError
import re

class TestCloudFormationValidation(unittest.TestCase):
    """Infrastructure tests using CloudFormation template validation"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.region = os.environ.get('AWS_REGION', 'us-east-1')
        cls.infrastructure_dir = Path(__file__).parent.parent.parent / 'infrastructure'
        
        # Initialize AWS client
        try:
            cls.cloudformation_client = boto3.client('cloudformation', region_name=cls.region)
            cls.aws_available = True
        except (NoCredentialsError, Exception):
            cls.aws_available = False
            print("Warning: AWS credentials not available. Some tests will be skipped.")
        
        # Template files to validate
        cls.template_files = {
            'vpc-network.yaml': 'VPC and networking infrastructure',
            'alb.yaml': 'Application Load Balancer',
            'ec2-autoscaling.yaml': 'EC2 Launch Template and Auto Scaling Group',
            'rds.yaml': 'RDS database',
            'monitoring.yaml': 'CloudWatch monitoring and SNS alerting',
            'cost-monitoring.yaml': 'Cost monitoring and billing alerts'
        }
    
    def load_template(self, template_name):
        """Load CloudFormation template from file"""
        template_path = self.infrastructure_dir / template_name
        
        if not template_path.exists():
            self.skipTest(f"Template file not found: {template_path}")
        
        try:
            with open(template_path, 'r') as f:
                if template_name.endswith('.yaml') or template_name.endswith('.yml'):
                    return yaml.safe_load(f)
                else:
                    return json.load(f)
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            self.fail(f"Failed to parse template {template_name}: {e}")
    
    def test_template_syntax_validation(self):
        """Test that all CloudFormation templates have valid syntax"""
        for template_name, description in self.template_files.items():
            with self.subTest(template=template_name):
                print(f"Validating syntax for {template_name} ({description})")
                
                template = self.load_template(template_name)
                
                # Basic structure validation
                self.assertIn('AWSTemplateFormatVersion', template, 
                            f"Missing AWSTemplateFormatVersion in {template_name}")
                self.assertIn('Description', template, 
                            f"Missing Description in {template_name}")
                self.assertIn('Resources', template, 
                            f"Missing Resources section in {template_name}")
                
                # Validate AWSTemplateFormatVersion
                self.assertEqual(template['AWSTemplateFormatVersion'], '2010-09-09',
                               f"Invalid AWSTemplateFormatVersion in {template_name}")
                
                # Validate Resources section is not empty
                self.assertGreater(len(template['Resources']), 0,
                                 f"Resources section is empty in {template_name}")
    
    def test_template_aws_validation(self):
        """Test CloudFormation template validation using AWS API"""
        if not self.aws_available:
            self.skipTest("AWS credentials not available")
        
        for template_name, description in self.template_files.items():
            with self.subTest(template=template_name):
                print(f"AWS validation for {template_name} ({description})")
                
                template_path = self.infrastructure_dir / template_name
                if not template_path.exists():
                    self.skipTest(f"Template file not found: {template_path}")
                
                try:
                    with open(template_path, 'r') as f:
                        template_body = f.read()
                    
                    # Validate template with AWS
                    response = self.cloudformation_client.validate_template(
                        TemplateBody=template_body
                    )
                    
                    # Verify response contains expected fields
                    self.assertIn('Parameters', response)
                    self.assertIn('Description', response)
                    
                    print(f"✓ {template_name} passed AWS validation")
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    self.fail(f"AWS validation failed for {template_name}: {error_code} - {error_message}")
                except Exception as e:
                    self.fail(f"Unexpected error validating {template_name}: {e}")
    
    def test_parameter_validation(self):
        """Test that template parameters are properly defined"""
        for template_name, description in self.template_files.items():
            with self.subTest(template=template_name):
                template = self.load_template(template_name)
                
                if 'Parameters' in template:
                    parameters = template['Parameters']
                    
                    for param_name, param_config in parameters.items():
                        # Validate parameter structure
                        self.assertIn('Type', param_config,
                                    f"Parameter {param_name} missing Type in {template_name}")
                        
                        # Validate parameter types
                        valid_types = [
                            'String', 'Number', 'List<Number>', 'CommaDelimitedList',
                            'AWS::EC2::AvailabilityZone::Name', 'AWS::EC2::Image::Id',
                            'AWS::EC2::Instance::Id', 'AWS::EC2::KeyPair::KeyName',
                            'AWS::EC2::SecurityGroup::GroupName', 'AWS::EC2::SecurityGroup::Id',
                            'AWS::EC2::Subnet::Id', 'AWS::EC2::Volume::Id',
                            'AWS::EC2::VPC::Id', 'AWS::Route53::HostedZone::Id',
                            'AWS::SSM::Parameter::Name', 'AWS::SSM::Parameter::Value<String>',
                            'List<AWS::EC2::AvailabilityZone::Name>', 'List<AWS::EC2::Image::Id>',
                            'List<AWS::EC2::Instance::Id>', 'List<AWS::EC2::SecurityGroup::GroupName>',
                            'List<AWS::EC2::SecurityGroup::Id>', 'List<AWS::EC2::Subnet::Id>',
                            'List<AWS::EC2::Volume::Id>', 'List<AWS::EC2::VPC::Id>',
                            'List<AWS::Route53::HostedZone::Id>'
                        ]
                        
                        self.assertIn(param_config['Type'], valid_types,
                                    f"Invalid parameter type {param_config['Type']} for {param_name} in {template_name}")
                        
                        # Check for description
                        if 'Description' not in param_config:
                            print(f"Warning: Parameter {param_name} in {template_name} missing description")
    
    def test_resource_validation(self):
        """Test that resources are properly defined"""
        for template_name, description in self.template_files.items():
            with self.subTest(template=template_name):
                template = self.load_template(template_name)
                resources = template['Resources']
                
                for resource_name, resource_config in resources.items():
                    # Validate resource structure
                    self.assertIn('Type', resource_config,
                                f"Resource {resource_name} missing Type in {template_name}")
                    
                    # Validate resource type format
                    resource_type = resource_config['Type']
                    type_pattern = r'^AWS::[A-Za-z0-9]+::[A-Za-z0-9]+$'
                    self.assertRegex(resource_type, type_pattern,
                                   f"Invalid resource type format {resource_type} for {resource_name} in {template_name}")
                    
                    # Check for Properties (most resources should have them)
                    if resource_type not in ['AWS::CloudFormation::WaitConditionHandle']:
                        if 'Properties' not in resource_config:
                            print(f"Warning: Resource {resource_name} in {template_name} has no Properties")
    
    def test_output_validation(self):
        """Test that outputs are properly defined"""
        for template_name, description in self.template_files.items():
            with self.subTest(template=template_name):
                template = self.load_template(template_name)
                
                if 'Outputs' in template:
                    outputs = template['Outputs']
                    
                    for output_name, output_config in outputs.items():
                        # Validate output structure
                        self.assertIn('Value', output_config,
                                    f"Output {output_name} missing Value in {template_name}")
                        
                        # Check for description
                        if 'Description' not in output_config:
                            print(f"Warning: Output {output_name} in {template_name} missing description")
                        
                        # Check for Export if it's a cross-stack reference
                        if 'Export' in output_config:
                            export_config = output_config['Export']
                            self.assertIn('Name', export_config,
                                        f"Export in output {output_name} missing Name in {template_name}")
    
    def test_free_tier_compliance(self):
        """Test that templates comply with AWS free tier limits"""
        # VPC template compliance
        vpc_template = self.load_template('vpc-network.yaml')
        
        # Check NAT Gateway count (should be 1 for free tier)
        nat_gateways = [
            resource for resource_name, resource in vpc_template['Resources'].items()
            if resource['Type'] == 'AWS::EC2::NatGateway'
        ]
        self.assertLessEqual(len(nat_gateways), 1, 
                           "Too many NAT Gateways for free tier compliance")
        
        # ALB template compliance
        alb_template = self.load_template('alb.yaml')
        
        # Check that access logs are disabled (costs money)
        alb_resources = [
            resource for resource_name, resource in alb_template['Resources'].items()
            if resource['Type'] == 'AWS::ElasticLoadBalancingV2::LoadBalancer'
        ]
        
        for alb in alb_resources:
            if 'Properties' in alb and 'LoadBalancerAttributes' in alb['Properties']:
                attributes = alb['Properties']['LoadBalancerAttributes']
                access_logs_attr = next(
                    (attr for attr in attributes if attr['Key'] == 'access_logs.s3.enabled'),
                    None
                )
                if access_logs_attr:
                    self.assertEqual(access_logs_attr['Value'], 'false',
                                   "Access logs should be disabled for free tier")
        
        # EC2 template compliance
        ec2_template = self.load_template('ec2-autoscaling.yaml')
        
        # Check instance types (should be t2.micro or t3.micro)
        if 'Parameters' in ec2_template and 'InstanceType' in ec2_template['Parameters']:
            instance_type_param = ec2_template['Parameters']['InstanceType']
            if 'AllowedValues' in instance_type_param:
                allowed_values = instance_type_param['AllowedValues']
                free_tier_types = ['t2.micro', 't3.micro']
                self.assertTrue(
                    any(ft_type in allowed_values for ft_type in free_tier_types),
                    "No free tier instance types in allowed values"
                )
        
        # Check max size for Auto Scaling Group
        if 'Parameters' in ec2_template and 'MaxSize' in ec2_template['Parameters']:
            max_size_param = ec2_template['Parameters']['MaxSize']
            if 'Default' in max_size_param:
                self.assertLessEqual(max_size_param['Default'], 5,
                                   "Max size too high for free tier")
    
    def test_security_best_practices(self):
        """Test that templates follow security best practices"""
        # VPC template security
        vpc_template = self.load_template('vpc-network.yaml')
        
        # Check that security groups follow least privilege
        security_groups = [
            (name, resource) for name, resource in vpc_template['Resources'].items()
            if resource['Type'] == 'AWS::EC2::SecurityGroup'
        ]
        
        for sg_name, sg_resource in security_groups:
            if 'Properties' in sg_resource:
                properties = sg_resource['Properties']
                
                # Check ingress rules
                if 'SecurityGroupIngress' in properties:
                    for rule in properties['SecurityGroupIngress']:
                        # Warn about overly permissive rules
                        if rule.get('CidrIp') == '0.0.0.0/0':
                            # Only allow for ALB security group on standard ports
                            if 'alb' not in sg_name.lower():
                                allowed_ports = [80, 443]
                                if rule.get('FromPort') not in allowed_ports:
                                    print(f"Warning: Potentially insecure rule in {sg_name}: {rule}")
        
        # EC2 template security
        ec2_template = self.load_template('ec2-autoscaling.yaml')
        
        # Check that IAM roles follow least privilege
        iam_roles = [
            (name, resource) for name, resource in ec2_template['Resources'].items()
            if resource['Type'] == 'AWS::IAM::Role'
        ]
        
        for role_name, role_resource in iam_roles:
            if 'Properties' in role_resource and 'Policies' in role_resource['Properties']:
                for policy in role_resource['Properties']['Policies']:
                    if 'PolicyDocument' in policy:
                        statements = policy['PolicyDocument'].get('Statement', [])
                        for statement in statements:
                            # Check for overly broad permissions
                            if statement.get('Effect') == 'Allow':
                                actions = statement.get('Action', [])
                                if isinstance(actions, str):
                                    actions = [actions]
                                
                                # Warn about wildcard actions
                                for action in actions:
                                    if action == '*':
                                        print(f"Warning: Wildcard action in {role_name}: {statement}")
    
    def test_resource_dependencies(self):
        """Test that resource dependencies are properly defined"""
        for template_name, description in self.template_files.items():
            with self.subTest(template=template_name):
                template = self.load_template(template_name)
                resources = template['Resources']
                
                # Track resource references
                resource_refs = {}
                
                for resource_name, resource_config in resources.items():
                    # Find Ref and GetAtt functions
                    resource_str = json.dumps(resource_config)
                    
                    # Find Ref references
                    ref_matches = re.findall(r'"Ref":\s*"([^"]+)"', resource_str)
                    getatt_matches = re.findall(r'"Fn::GetAtt":\s*\[\s*"([^"]+)"', resource_str)
                    
                    all_refs = ref_matches + getatt_matches
                    resource_refs[resource_name] = all_refs
                
                # Validate that referenced resources exist
                for resource_name, refs in resource_refs.items():
                    for ref in refs:
                        # Skip AWS pseudo parameters
                        aws_params = [
                            'AWS::AccountId', 'AWS::NotificationARNs', 'AWS::NoValue',
                            'AWS::Partition', 'AWS::Region', 'AWS::StackId',
                            'AWS::StackName', 'AWS::URLSuffix'
                        ]
                        
                        if ref not in aws_params:
                            # Check if it's a parameter or resource
                            parameters = template.get('Parameters', {})
                            if ref not in parameters and ref not in resources:
                                print(f"Warning: {resource_name} references undefined resource/parameter: {ref}")
    
    def test_template_metadata(self):
        """Test that templates have proper metadata and documentation"""
        for template_name, description in self.template_files.items():
            with self.subTest(template=template_name):
                template = self.load_template(template_name)
                
                # Check description quality
                desc = template.get('Description', '')
                self.assertGreater(len(desc), 20,
                                 f"Description too short in {template_name}")
                self.assertIn('dominoes', desc.lower(),
                            f"Description should mention the application in {template_name}")
                
                # Check for cost optimization notes in outputs
                outputs = template.get('Outputs', {})
                cost_outputs = [
                    output for output_name, output in outputs.items()
                    if 'cost' in output_name.lower() or 'free' in output_name.lower()
                ]
                
                if template_name in ['vpc-network.yaml', 'alb.yaml', 'ec2-autoscaling.yaml']:
                    self.assertGreater(len(cost_outputs), 0,
                                     f"Missing cost optimization outputs in {template_name}")

if __name__ == '__main__':
    unittest.main(verbosity=2)
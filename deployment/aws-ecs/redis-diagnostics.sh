#!/bin/bash
# Redis ElastiCache Diagnostics Script
# Run this to verify ElastiCache and ECS connectivity

set -e

echo "🔍 Redis ElastiCache Diagnostics"
echo "================================"

# Check ElastiCache cluster status
echo "📊 ElastiCache Cluster Status:"
aws elasticache describe-cache-clusters \
  --cache-cluster-id binomial-redis \
  --show-cache-node-info \
  --query 'CacheClusters[0].{
    Status:CacheClusterStatus,
    Engine:Engine,
    EngineVersion:EngineVersion,
    NumNodes:NumCacheNodes,
    NodeType:CacheNodeType,
    SecurityGroups:SecurityGroups,
    SubnetGroup:CacheSubnetGroupName
  }' \
  --output table \
  --region us-east-1

# Check replication group (if cluster mode)
echo -e "\n🔄 Replication Group Status:"
aws elasticache describe-replication-groups \
  --replication-group-id binomial-redis \
  --query 'ReplicationGroups[0].{
    Status:Status,
    ClusterEnabled:ClusterEnabled,
    MultiAZ:MultiAZ,
    NumNodeGroups:NumNodeGroups,
    SecurityGroups:SecurityGroups
  }' \
  --output table \
  --region us-east-1 2>/dev/null || echo "No replication group found"

# Get individual node endpoints
echo -e "\n🌐 Cache Node Endpoints:"
aws elasticache describe-cache-clusters \
  --cache-cluster-id binomial-redis \
  --show-cache-node-info \
  --query 'CacheClusters[0].CacheNodes[*].{
    NodeId:CacheNodeId,
    Endpoint:Endpoint.Address,
    Port:Endpoint.Port,
    Status:CacheNodeStatus
  }' \
  --output table \
  --region us-east-1

# Check ECS service network configuration
echo -e "\n🐳 ECS Service Network Configuration:"
aws ecs describe-services \
  --cluster binomial-sentry-cluster \
  --services binomial-sentry-backend-service-b9ze202w \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.{
    Subnets:subnets,
    SecurityGroups:securityGroups,
    AssignPublicIp:assignPublicIp
  }' \
  --output table \
  --region us-east-1

# Get security group details for both services
echo -e "\n🛡️  Security Group Analysis:"
ECS_SG=$(aws ecs describe-services \
  --cluster binomial-sentry-cluster \
  --services binomial-sentry-backend-service-b9ze202w \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups[0]' \
  --output text \
  --region us-east-1)

echo "ECS Security Group: $ECS_SG"

# Check if ECS security group has outbound rules for Redis
aws ec2 describe-security-groups \
  --group-ids $ECS_SG \
  --query 'SecurityGroups[0].IpPermissionsEgress[?IpProtocol==`tcp` && (ToPort==`6379` || ToPort==`-1`)]' \
  --output table \
  --region us-east-1

# Get ElastiCache subnet group and VPC info
echo -e "\n🌍 VPC and Subnet Configuration:"
aws elasticache describe-cache-subnet-groups \
  --query 'CacheSubnetGroups[?starts_with(CacheSubnetGroupName, `binomial`)].{
    Name:CacheSubnetGroupName,
    VPC:VpcId,
    Subnets:Subnets[*].SubnetId
  }' \
  --output table \
  --region us-east-1

echo -e "\n✅ Diagnostics complete. Check for any connectivity issues above."
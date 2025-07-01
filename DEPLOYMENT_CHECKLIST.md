# Azure Deployment Checklist

## Pre-Deployment Checklist
- [ ] Azure account with active subscription
- [ ] Azure CLI installed and configured
- [ ] OpenRouter API key ready
- [ ] Code tested locally
- [ ] All dependencies listed in requirements.txt
- [ ] Environment variables documented

## Deployment Steps
- [ ] Run deployment script (`deploy-to-azure.ps1` or `deploy-to-azure.sh`)
- [ ] Configure OpenRouter API key
- [ ] Deploy code via Git or ZIP
- [ ] Test the deployed application
- [ ] Configure custom domain (if needed)
- [ ] Set up monitoring and alerts

## Post-Deployment Verification
- [ ] App loads successfully at Azure URL
- [ ] File upload functionality works
- [ ] Audio extraction works (ffmpeg available)
- [ ] Whisper transcription works
- [ ] OpenRouter translation works
- [ ] Subtitle generation works
- [ ] Video output with burned subtitles works
- [ ] Logs are being generated properly

## Performance Optimization
- [ ] Monitor memory and CPU usage
- [ ] Optimize Whisper model size if needed
- [ ] Configure auto-scaling if necessary
- [ ] Set up Application Insights for detailed monitoring
- [ ] Configure CDN for static assets if needed

## Security Checklist
- [ ] HTTPS only enabled
- [ ] API keys stored securely
- [ ] CORS configured properly
- [ ] File upload limits configured
- [ ] Authentication configured (if needed)

## Monitoring and Maintenance
- [ ] Set up alerts for errors and performance issues
- [ ] Configure log retention policies
- [ ] Set up backup strategies for important data
- [ ] Plan for regular updates and maintenance

## Troubleshooting Resources
- [ ] Application logs accessible via Azure Portal
- [ ] Log streaming configured
- [ ] SSH access to container configured
- [ ] Application Insights configured for detailed telemetry

## Cost Management
- [ ] Monitor daily/monthly costs
- [ ] Set up cost alerts
- [ ] Optimize resource usage
- [ ] Consider reserved instances for production
